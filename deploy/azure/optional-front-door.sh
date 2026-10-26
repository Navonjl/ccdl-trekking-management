#!/usr/bin/env bash
# Not part of the lab run. Azure refuses Front Door on Free Trial and Student
# subscriptions ("Free Trial and Student account is forbidden for Azure
# Frontdoor resources"), so 04-edge.sh uses the AKS application routing add-on
# instead. On a pay-as-you-go subscription this script adds the production edge
# from the design: Azure Front Door in front of everything. /api/* goes to the AKS load
# balancer, everything else to the static site in Blob Storage, so the browser
# sees one HTTPS origin. A WAF policy rate-limits login and booking.
#
# Front Door Standard has no free tier: 35 USD a month before traffic. It is
# safe to delete the profile between demos and re-run this script.
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/optional-front-door.log"
API_HOST="$SITE_HOST"
: > "$LOG"

WEB_HOST=$(az storage account show -g "$RG" -n "$STORAGE" --query primaryEndpoints.web -o tsv | sed 's|https://||; s|/$||')

missing az afd profile show -g "$RG" --profile-name "$FD" &&
  run az afd profile create --resource-group "$RG" --profile-name "$FD" \
    --sku Standard_AzureFrontDoor -o table

missing az afd endpoint show -g "$RG" --profile-name "$FD" --endpoint-name "$FD_ENDPOINT" &&
  run az afd endpoint create --resource-group "$RG" --profile-name "$FD" \
    --endpoint-name "$FD_ENDPOINT" --enabled-state Enabled -o table

# API origin: the AKS load balancer, probed on the readiness endpoint.
missing az afd origin-group show -g "$RG" --profile-name "$FD" --origin-group-name api &&
  run az afd origin-group create --resource-group "$RG" --profile-name "$FD" \
    --origin-group-name api --probe-request-type GET --probe-protocol Http \
    --probe-interval-in-seconds 60 --probe-path /api/health \
    --sample-size 4 --successful-samples-required 3 --additional-latency-in-milliseconds 50 -o table
missing az afd origin show -g "$RG" --profile-name "$FD" --origin-group-name api --origin-name aks &&
  run az afd origin create --resource-group "$RG" --profile-name "$FD" \
    --origin-group-name api --origin-name aks --host-name "$API_HOST" \
    --origin-host-header "$API_HOST" --http-port 80 --https-port 443 \
    --priority 1 --weight 1000 --enabled-state Enabled -o table

# Web origin: the static website endpoint of the storage account.
missing az afd origin-group show -g "$RG" --profile-name "$FD" --origin-group-name web &&
  run az afd origin-group create --resource-group "$RG" --profile-name "$FD" \
    --origin-group-name web --probe-request-type HEAD --probe-protocol Https \
    --probe-interval-in-seconds 120 --probe-path / \
    --sample-size 4 --successful-samples-required 3 --additional-latency-in-milliseconds 50 -o table
missing az afd origin show -g "$RG" --profile-name "$FD" --origin-group-name web --origin-name blob &&
  run az afd origin create --resource-group "$RG" --profile-name "$FD" \
    --origin-group-name web --origin-name blob --host-name "$WEB_HOST" \
    --origin-host-header "$WEB_HOST" --http-port 80 --https-port 443 \
    --priority 1 --weight 1000 --enabled-state Enabled -o table

missing az afd route show -g "$RG" --profile-name "$FD" --endpoint-name "$FD_ENDPOINT" --route-name api &&
  run az afd route create --resource-group "$RG" --profile-name "$FD" \
    --endpoint-name "$FD_ENDPOINT" --route-name api --origin-group api \
    --patterns-to-match '/api/*' --supported-protocols Https Http \
    --forwarding-protocol HttpOnly --https-redirect Enabled \
    --link-to-default-domain Enabled -o table
missing az afd route show -g "$RG" --profile-name "$FD" --endpoint-name "$FD_ENDPOINT" --route-name web &&
  run az afd route create --resource-group "$RG" --profile-name "$FD" \
    --endpoint-name "$FD_ENDPOINT" --route-name web --origin-group web \
    --patterns-to-match '/*' --supported-protocols Https Http \
    --forwarding-protocol HttpsOnly --https-redirect Enabled \
    --link-to-default-domain Enabled \
    --cache-configuration '{query-string-caching-behavior:IgnoreQueryString,compression-settings:{is-compression-enabled:true,content-types-to-compress:[text/html,text/css,application/javascript,image/svg+xml]}}' \
    -o table

# --- WAF: rate limits on the two endpoints worth protecting ------------------
missing az network front-door waf-policy show -g "$RG" -n "$WAF" &&
  run az network front-door waf-policy create --resource-group "$RG" --name "$WAF" \
    --sku Standard_AzureFrontDoor --mode Prevention -o table

# 20 login attempts per minute per client IP slows credential stuffing.
run az network front-door waf-policy rule create --resource-group "$RG" --policy-name "$WAF" \
  --name LoginRateLimit --priority 10 --rule-type RateLimitRule --action Block \
  --rate-limit-threshold 20 --rate-limit-duration 1 \
  --match-variable RequestUri --operator Contains --values /api/accounts/login -o none
# 30 booking requests per minute stops one script hogging a popular trek.
run az network front-door waf-policy rule create --resource-group "$RG" --policy-name "$WAF" \
  --name BookingRateLimit --priority 20 --rule-type RateLimitRule --action Block \
  --rate-limit-threshold 30 --rate-limit-duration 1 \
  --match-variable RequestUri --operator Contains --values /api/bookings -o none
run az network front-door waf-policy rule list --resource-group "$RG" --policy-name "$WAF" \
  --query '[].{name:name, priority:priority, type:ruleType, limit:rateLimitThreshold, action:action}' -o table

WAF_ID=$(az network front-door waf-policy show -g "$RG" -n "$WAF" --query id -o tsv)
ENDPOINT_ID=$(az afd endpoint show -g "$RG" --profile-name "$FD" --endpoint-name "$FD_ENDPOINT" --query id -o tsv)
missing az afd security-policy show -g "$RG" --profile-name "$FD" -n waf &&
  run az afd security-policy create --resource-group "$RG" --profile-name "$FD" -n waf \
    --web-application-firewall "{waf-policy:{id:'$WAF_ID'},associations:[{domains:[{id:'$ENDPOINT_ID'}],patterns-to-match:['/*']}]}" \
    -o none

FD_HOST=$(az afd endpoint show -g "$RG" --profile-name "$FD" --endpoint-name "$FD_ENDPOINT" --query hostName -o tsv)
remember FD_HOST "$FD_HOST"
run az afd endpoint show -g "$RG" --profile-name "$FD" --endpoint-name "$FD_ENDPOINT" \
  --query '{host:hostName, state:deploymentStatus, enabled:enabledState}' -o table

# Front Door takes a few minutes to push new routes to its edge.
run curl -sS --retry 30 --retry-delay 20 --retry-all-errors --fail "https://$FD_HOST/api/health"
echo
