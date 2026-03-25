#!/usr/bin/env bash
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-$HOME/Workspace/MasRobo/CrewClaw/infra/compose}"
API_CONTAINER="${API_CONTAINER:-crewclaw-api}"
USER_SUBJECT="${USER_SUBJECT:-authentik:e2e-user-001}"
ADMIN_SUBJECT="${ADMIN_SUBJECT:-authentik:e2e-admin-001}"

api_call() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local subject="${4:-}"

  if [[ -n "$body" ]]; then
    docker exec "$API_CONTAINER" sh -lc "curl -sS -X ${method} 'http://127.0.0.1:8000${path}' -H 'Content-Type: application/json' ${subject:+-H 'X-Authentik-Subject: ${subject}'} -d '${body}'"
  else
    docker exec "$API_CONTAINER" sh -lc "curl -sS -X ${method} 'http://127.0.0.1:8000${path}' ${subject:+-H 'X-Authentik-Subject: ${subject}'}"
  fi
}

json_get() {
  local key="$1"
  python3 -c "import json,sys; print(json.load(sys.stdin).get('${key}',''))"
}

echo "[1/7] 检查 compose 服务状态"
docker compose --env-file "$COMPOSE_DIR/.env" -f "$COMPOSE_DIR/docker-compose.yml" ps >/dev/null

echo "[2/7] 同步 admin 用户（用于浏览器登录）"
admin_sync="$(api_call POST /internal/users/sync "{\"subjectId\":\"${ADMIN_SUBJECT}\"}")"
admin_user_id="$(printf '%s' "$admin_sync" | json_get userId)"
echo "admin userId=${admin_user_id}"

echo "[3/7] 同步业务用户"
user_sync="$(api_call POST /internal/users/sync "{\"subjectId\":\"${USER_SUBJECT}\"}")"
user_user_id="$(printf '%s' "$user_sync" | json_get userId)"
echo "user userId=${user_user_id}"

echo "[4/7] 确保 runtime binding 并获取 runtimeId"
binding="$(api_call POST "/internal/users/${user_user_id}/runtime-binding/ensure")"
runtime_id="$(printf '%s' "$binding" | json_get runtimeId)"
echo "runtimeId=${runtime_id}"

echo "[5/7] 触发 runtime 启动（真实 OpenClaw 容器）"
start_resp="$(api_call POST /api/v1/users/me/runtime/start "" "$USER_SUBJECT")"
task_id="$(printf '%s' "$start_resp" | json_get taskId)"
echo "taskId=${task_id}"

echo "[6/7] 轮询任务状态"
for _ in {1..15}; do
  task_resp="$(api_call GET "/api/v1/runtime/tasks/${task_id}" "" "$USER_SUBJECT")"
  task_status="$(printf '%s' "$task_resp" | json_get status)"
  echo "task status=${task_status}"
  if [[ "$task_status" == "running" || "$task_status" == "succeeded" ]]; then
    break
  fi
  sleep 2
done

echo "[7/7] 校验容器存在"
container_name="rt-${runtime_id}"
if docker ps --format '{{.Names}}' | awk -v n="$container_name" '$0==n{found=1} END{exit found?0:1}'; then
  echo "OK: OpenClaw 容器已运行: ${container_name}"
else
  echo "ERROR: 未发现运行中的容器 ${container_name}"
  docker ps -a --format 'table {{.Names}}\t{{.Status}}'
  exit 1
fi

binding_after_start="$(api_call POST "/internal/users/${user_user_id}/runtime-binding/ensure")"
browser_url="$(printf '%s' "$binding_after_start" | json_get browserUrl)"
echo "OpenClaw 浏览器入口: ${browser_url}"

echo ""
echo "下一步浏览器验证："
echo "1) 打开 http://localhost:9000/if/admin/ 用管理员账号登录 Authentik。"
echo "2) 打开 http://clawloops.localhost 用同一账号登录 ClawLoops。"
echo "3) 用户账号登录后，访问工作区入口并进入 OpenClaw。"
echo "4) 也可直接打开上面的 OpenClaw 浏览器入口验证容器 UI。"
