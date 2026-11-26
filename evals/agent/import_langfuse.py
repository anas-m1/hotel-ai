#!/usr/bin/env python3
"""Import repository scenarios into Langfuse; no inference or scoring is performed."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ANSWER_FIELDS = {'expected_json', 'required_answer_terms', 'required_answer_groups',
                 'forbidden_answer_terms'}


def map_suite(path: Path, dataset_name: str) -> tuple[dict, list[dict]]:
    raw = path.read_bytes()
    suite = json.loads(raw)
    items = []
    seen = set()
    for case in suite['cases']:
        case_id = case['id']
        if case_id in seen:
            raise ValueError('Duplicate case ID')
        seen.add(case_id)
        turns = case.get('turns', [case])
        if not turns or any(not isinstance(t.get('message'), str) for t in turns):
            raise ValueError('Every turn must have a message')
        items.append({
            'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'hotel-ai/{dataset_name}/{case_id}')),
            'dataset_name': dataset_name,
            'input': {'turns': [{'message': t['message']} for t in turns]},
            'expected_output': {'turns': [
                {k: v for k, v in t.items() if k in ANSWER_FIELDS} for t in turns
            ]},
            'metadata': {
                'case_id': case_id,
                'category': case.get('category'),
                'mapping_version': 'hotel-agent-turns-v1',
                'tool_rules_by_turn': [
                    {k: v for k, v in t.items()
                     if k not in ANSWER_FIELDS | {'message', 'id', 'category'}}
                    for t in turns
                ],
                # Preserve the exact source definition for the existing scorer/runner.
                'source_case': case,
            },
        })
    return {
        'suite': suite['suite'], 'split': suite.get('split'),
        'source_file': path.name, 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'fixture': suite.get('fixture'), 'mapping_version': 'hotel-agent-turns-v1',
    }, items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Write to Langfuse; default is dry-run')
    parser.add_argument('--host', default='http://localhost:3000')
    parser.add_argument('--env-file', type=Path, default=ROOT / 'infra/docker/booking-assistant.env')
    args = parser.parse_args()
    # Validate both complete suites before the first write.
    plans = [(name, *map_suite(HERE / filename, name)) for name, filename in [
        ('hotel-agent-dev', 'agent_cases.json'),
        ('hotel-agent-heldout', 'heldout_cases.json'),
    ]]
    for name, metadata, items in plans:
        print(f'{name}: {len(items)} scenarios, {sum(len(i["input"]["turns"]) for i in items)} turns; '
              f'source {metadata["source_sha256"][:12]}')
    if not args.apply:
        print('Dry-run complete. No credentials loaded and no requests made.')
        return 0
    from dotenv import dotenv_values
    from langfuse import Langfuse
    values = dotenv_values(args.env_file, interpolate=False)
    keys = {k: os.environ.get(k) or values.get(k) for k in
            ['LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY']}
    if not all(keys.values()):
        raise ValueError('Langfuse credentials are not configured')
    client = Langfuse(public_key=keys['LANGFUSE_PUBLIC_KEY'],
                      secret_key=keys['LANGFUSE_SECRET_KEY'], host=args.host, timeout=60)
    try:
        for name, metadata, items in plans:
            # create is an upsert by name; item IDs are stable and dataset-specific.
            client.create_dataset(name=name, metadata=metadata,
                                  description='Repository hotel-agent scenarios. Custom runner required; '
                                              'tool rules are evaluated by code, not automatically by Langfuse.')
            for item in items:
                client.create_dataset_item(**item)
            stored = client.get_dataset(name)
            expected_ids = {i['id'] for i in items}
            actual_ids = {i.id for i in stored.items}
            if not expected_ids <= actual_ids:
                raise RuntimeError('Read-back verification failed')
            print(f'Imported and verified {len(expected_ids)} items in {name}; '
                  f'{len(actual_ids)} total stored items.')
    finally:
        client.shutdown()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # SDK exception bodies may contain request details: never print them.
        print(f'Import failed ({type(exc).__name__}); no credential values displayed.')
        raise SystemExit(1) from None
