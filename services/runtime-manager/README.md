# Runtime Manager

Internal RuntimeManager service for ClawLoops.

## Endpoints

- `POST /internal/runtime-manager/containers/ensure-running`
- `POST /internal/runtime-manager/containers/stop`
- `POST /internal/runtime-manager/containers/delete`
- `GET /internal/runtime-manager/containers/{runtimeId}`
- `GET /healthz`
- `GET /readyz`
