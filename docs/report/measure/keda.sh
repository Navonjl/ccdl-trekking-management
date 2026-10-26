#!/usr/bin/env bash
# Queue 3000 CSV exports at once and sample the worker replica count and the
# Service Bus queue length every 10 seconds, to show KEDA scaling the workers
# out on queue length and back in once the queue drains.
#   docs/report/measure/keda.sh > docs/report/data/keda.csv
set -euo pipefail
export KUBECONFIG="$(dirname "$0")/../../../deploy/azure/.kubeconfig"
JOBS=${JOBS:-3000}

# The jobs are queued by a Kubernetes Job of four parallel pods running the
# app image: each has its own broker connection (the Service Bus channel is
# not thread-safe) and its own memory, so the API pods are not squeezed.
IMAGE=$(kubectl -n hitc get deploy trek-api -o jsonpath='{.spec.template.spec.containers[0].image}')
kubectl -n hitc delete job keda-load --ignore-not-found >/dev/null
kubectl -n hitc apply -f - >/dev/null <<YAML
apiVersion: batch/v1
kind: Job
metadata: { name: keda-load }
spec:
  parallelism: 4
  completions: 4
  backoffLimit: 0
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: load
          image: $IMAGE
          envFrom: [{ secretRef: { name: hitc-secrets } }]
          resources:
            requests: { cpu: 50m, memory: 160Mi }
            limits: { memory: 384Mi }
          command:
            - python
            - -c
            - |
              from app import create_app
              from app.models import User
              from app.tasks import export_bookings_csv
              app = create_app()
              with app.app_context():
                  ids = [u.id for u in User.query.all()]
                  for n in range($((JOBS / 4))):
                      export_bookings_csv.delay(ids[n % len(ids)])
YAML

echo "seconds,queued,worker_replicas,worker_ready"
START=$(date +%s)
while (( $(date +%s) - START < 420 )); do
  queued=$(az servicebus queue show -g hitc-rg --namespace-name hitc602bus -n celery \
    --query countDetails.activeMessageCount -o tsv 2>/dev/null || echo "")
  read -r desired ready < <(kubectl -n hitc get deploy trek-worker \
    -o jsonpath='{.spec.replicas} {.status.readyReplicas}{"\n"}') || true
  echo "$(( $(date +%s) - START )),$queued,$desired,${ready:-0}"
  sleep 10
done
kubectl -n hitc get job keda-load -o jsonpath='{.status.succeeded}/4 pods succeeded{"\n"}' >&2
