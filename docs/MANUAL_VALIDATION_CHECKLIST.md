# Agent Eval MVP Manual Validation Checklist

Use this checklist to validate the current MVP in a local, single-operator setup.

## Scope under test

- Task type: `classification`
- Target type: `http`
- Case import: manual inline cases
- Run execution: background run execution via FastAPI `BackgroundTasks`

## Prerequisites

- [ ] PostgreSQL is running
- [ ] API starts successfully
- [ ] `/health` returns `200`
- [ ] `/ready` returns `200`
- [ ] Migrations apply cleanly on a fresh database

## Setup sanity checks

- [ ] Create a dataset
- [ ] List datasets and confirm the new dataset appears
- [ ] Fetch the dataset by ID
- [ ] Create an HTTP target
- [ ] List targets and confirm the new target appears
- [ ] Fetch the target by ID

## Happy-path validation

### 1) Create a dataset

- [ ] Create a dataset with:
  - [ ] `name`
  - [ ] `task_type=classification`
  - [ ] optional `description`
- [ ] Confirm the response is `201`
- [ ] Confirm returned fields match what you sent

### 2) Import dataset cases

- [ ] Import 2–5 classification cases into the dataset
- [ ] Confirm the response is `201`
- [ ] Confirm `imported_count` matches the number of cases
- [ ] Confirm each case is persisted and returned
- [ ] Confirm case ordering is stable when listed

### 3) Create a target

- [ ] Create an HTTP target with:
  - [ ] `name`
  - [ ] `target_type=http`
  - [ ] `base_url`
  - [ ] `endpoint_path`
  - [ ] optional `timeout_ms`
  - [ ] optional `headers`
- [ ] Confirm the response is `201`
- [ ] Confirm the target can be fetched by ID

### 4) Create and execute a run

- [ ] Create a run using the dataset and target IDs
- [ ] Confirm the response is `201`
- [ ] Confirm initial status is `queued`
- [ ] Wait for the run to complete
- [ ] Confirm final status is `completed`
- [ ] Confirm run summary fields are populated
- [ ] Confirm per-case results are persisted
- [ ] Confirm `/runs/{run_id}/summary` returns the run and results together
- [ ] Confirm `/runs/{run_id}/results` returns the result list

### 5) Validate success metrics

- [ ] Confirm summary totals are correct
- [ ] Confirm `passed` count matches expected behavior
- [ ] Confirm `failed`, `error`, and `invalid_case` are `0` for a fully passing run
- [ ] Confirm `metrics_json.accuracy` is `1.0` for a fully passing run
- [ ] Confirm `metrics_json.average_latency_ms` is present and reasonable

## Failure-path validation

### Target returns non-200

- [ ] Create a case that causes the target to return a non-200 status
- [ ] Confirm the run completes with an `error` result
- [ ] Confirm `error_type=http_status_error`
- [ ] Confirm run summary counts the result under `error`

### Target times out

- [ ] Create a case that sleeps longer than the target timeout
- [ ] Confirm the run completes with an `error` result
- [ ] Confirm `error_type=timeout`
- [ ] Confirm run summary counts the result under `error`

### Target returns invalid JSON

- [ ] Create a case that causes the target to return invalid JSON
- [ ] Confirm the run completes with an `error` result
- [ ] Confirm `error_type=invalid_json`

### Target returns malformed payload

- [ ] Create a case that returns JSON without a string `label`
- [ ] Confirm the result status is `error`
- [ ] Confirm `error_type=invalid_response`

### Wrong label

- [ ] Create a case where the target returns the wrong label
- [ ] Confirm the result status is `failed`
- [ ] Confirm score is `0.0`

### Invalid case contract

- [ ] Create a case with an invalid classification contract
- [ ] Confirm the result status is `invalid_case`
- [ ] Confirm the run still completes

## Dataset validation

- [ ] Reject duplicate `case_key` values within the same import payload
- [ ] Reject duplicate `case_key` values already present in the dataset
- [ ] Reject case/task type mismatches
- [ ] Confirm dataset pagination works with `limit` and `offset`
- [ ] Confirm dataset filtering by `task_type` works

## Target validation

- [ ] Reject duplicate target names
- [ ] Confirm target pagination works with `limit` and `offset`
- [ ] Confirm target filtering by `target_type` works
- [ ] Confirm target headers behave as expected in your local environment

## Run validation

- [ ] Confirm creating a run on an empty dataset is rejected
- [ ] Confirm runs can be listed
- [ ] Confirm filtering runs by `dataset_id` works
- [ ] Confirm filtering runs by `target_id` works
- [ ] Confirm filtering runs by `status` works
- [ ] Confirm pagination works on runs
- [ ] Confirm `queued -> running -> completed` state transitions occur as expected
- [ ] Confirm a background crash marks the run as `failed`
- [ ] Confirm a failed run has a useful `summary_json.run_error`

## Operational checks

- [ ] Restart the API while a slow run is executing
- [ ] Observe what happens to the run state
- [ ] Confirm whether partial work is lost
- [ ] Confirm you are comfortable with this behavior for MVP validation
- [ ] Kill the API during execution and repeat the same observation

## API coherence checks

- [ ] Confirm the visible MVP surface is only the current classification workflow
- [ ] Confirm any non-MVP task types are not presented as ready for validation
- [ ] Confirm any non-MVP import formats are not presented as ready for validation

## Manual validation exit criteria

You can treat the MVP as manually validated when:

- [ ] The happy path succeeds end to end
- [ ] The expected failure paths behave consistently
- [ ] Run summaries and per-case results are correct
- [ ] You understand the restart/kill behavior during execution
- [ ] You are satisfied the current surface matches the intended MVP scope
