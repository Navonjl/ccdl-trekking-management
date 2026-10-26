#!/usr/bin/env bash
# Step 4: the public HTTPS entry point. The AKS application routing add-on is
# Azure's managed NGINX ingress, free with the cluster; cert-manager gets a
# Let's Encrypt certificate for the load balancer's cloudapp.azure.com name.
# /api/* goes to the API pods and everything else to the static site in Blob
# Storage, so the browser sees one origin. NGINX rate limits on login and
# booking stand in for the WAF rules Front Door would have carried.
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/04-edge.log"
: > "$LOG"

[[ "$(az aks show -g "$RG" -n "$AKS" --query ingressProfile.webAppRouting.enabled -o tsv)" == true ]] ||
  run az aks approuting enable --resource-group "$RG" --name "$AKS" -o none
# The add-on's default controller requests a full CPU across two replicas;
# the chart brings its own controller, so drop the default one.
run az aks approuting update --resource-group "$RG" --name "$AKS" --nginx None -o none
# The setting stops the add-on managing the default controller but leaves the
# existing one running, so remove it.
run kubectl delete nginxingresscontroller default --ignore-not-found
run az aks show --resource-group "$RG" --name "$AKS" \
  --query '{appRouting:ingressProfile.webAppRouting.enabled}' -o table

# Install once. AKS's admissions enforcer edits cert-manager's webhook, which a
# later server-side apply by Helm reports as a conflict.
helm status cert-manager -n cert-manager >/dev/null 2>&1 ||
  run helm install cert-manager oci://quay.io/jetstack/charts/cert-manager \
    --version v1.21.2 --namespace cert-manager --create-namespace \
    --set crds.enabled=true --wait --timeout 5m

WEB_HOST=$(az storage account show -g "$RG" -n "$STORAGE" --query primaryEndpoints.web -o tsv | sed 's|https://||; s|/$||')
run helm upgrade hitc "$HERE/../helm/hitc" --namespace "$K8S_NAMESPACE" --reuse-values \
  --set edge.enabled=true --set edge.dnsLabel="$SITE_DNS_LABEL" \
  --set edge.host="$SITE_HOST" --set edge.webHost="$WEB_HOST" \
  --wait --timeout 5m

# Let's Encrypt issues the certificate once the DNS name resolves to the
# controller's load balancer, usually within two minutes.
run kubectl -n "$K8S_NAMESPACE" wait certificate/hitc-tls --for=condition=Ready --timeout=10m
run kubectl -n "$K8S_NAMESPACE" get ingress,certificate
run curl -sS --retry 10 --retry-delay 6 --retry-all-errors --fail "https://$SITE_HOST/api/health"
echo
run curl -sS --fail -o /dev/null -w 'front end: HTTP %{http_code}, %{size_download} bytes\n' "https://$SITE_HOST/"
