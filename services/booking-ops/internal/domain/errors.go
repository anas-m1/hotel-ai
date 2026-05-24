package domain

import "errors"

var (
	ErrNotFound      = errors.New("not found")
	ErrConflict      = errors.New("already exists")
	ErrVersionConflict = errors.New("version conflict — record was modified by another request")
)
