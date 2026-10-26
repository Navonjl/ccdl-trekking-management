{{/* Labels shared by every object in the chart. */}}
{{- define "hitc.labels" -}}
app.kubernetes.io/part-of: head-in-the-clouds
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* Pod spec pieces the API, worker and init job all need: the workload
     identity, the Key Vault mount that creates the hitc-secrets Secret, and
     the environment built from it. */}}
{{- define "hitc.podIdentity" -}}
serviceAccountName: {{ .Values.serviceAccountName }}
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
volumes:
  - name: keyvault
    csi:
      driver: secrets-store.csi.k8s.io
      readOnly: true
      volumeAttributes:
        secretProviderClass: hitc-keyvault
{{- end }}

{{- define "hitc.env" -}}
envFrom:
  - secretRef:
      name: hitc-secrets
env:
  - name: FLASK_DEBUG
    value: "0"
  - name: EXPORT_BLOB_ACCOUNT_URL
    value: {{ .Values.azure.exportBlobAccountUrl | quote }}
volumeMounts:
  - name: keyvault
    mountPath: /mnt/keyvault
    readOnly: true
{{- end }}
