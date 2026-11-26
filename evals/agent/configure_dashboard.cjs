// Run in the installed Langfuse worker with JSON config on stdin.
// Uses its Prisma/encryption helpers because 4.36's public dataset API does
// not expose webhook configuration. Never prints the supplied auth token.
const fs = require('node:fs');
const {createRequire} = require('node:module');
const installedRequire = createRequire('/app/worker/package.json');
const {prisma} = installedRequire('@langfuse/shared/src/db');
const {encryptSecretHeaders, createDisplayHeaders} = installedRequire('@langfuse/shared/src/server');
async function main() {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const url = 'http://hotel-agent-evals/experiments';
  const headers = {authorization: {secret: true, value: 'Bearer ' + config.token}};
  const names = ['hotel-agent-dev', 'hotel-agent-heldout'];
  await prisma.$transaction(async tx => {
    for (const name of names) {
      const dataset = await tx.dataset.findUnique({where: {projectId_name: {name, projectId: config.projectId}}});
      if (!dataset || (dataset.remoteExperimentUrl && dataset.remoteExperimentUrl !== url))
        throw new Error('Dataset missing or has an unrelated webhook; refusing overwrite');
      await tx.dataset.update({where: {id_projectId: {id: dataset.id, projectId: config.projectId}}, data: {
        remoteExperimentUrl: url, remoteExperimentEnabled: true,
        remoteExperimentPayload: JSON.stringify({run_name: config.runName || 'local-smoke-next', variant: config.variant || 'local',
          expected_model: config.model, dataset_version: config.datasetVersion,
          case_ids: [name === 'hotel-agent-dev' ? 'facts_HTL002' : 'paraphrase_marina'], repeats: 1}),
        remoteExperimentRequestHeaders: encryptSecretHeaders(headers),
        remoteExperimentDisplayHeaders: createDisplayHeaders(headers),
      }});
    }
  });
  console.log('Configured both dataset triggers; authentication header encrypted and masked.');
}
main().catch(e => {console.log('Dashboard setup failed (' + e.constructor.name + ')'); process.exitCode = 1;})
  .finally(async () => { await prisma.$disconnect(); process.exit(process.exitCode || 0); });
