#!/bin/sh
# Vault init script — configure les secrets pour Stonks en mode dev.
# Ce script est monté dans le conteneur Vault et peut être exécuté
# manuellement après le premier démarrage :
#   docker compose exec vault sh /vault-init.sh

set -e

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-dev-token}"

export VAULT_ADDR VAULT_TOKEN

echo "🔐 Vault init: writing stonks secrets..."

# Enable KV v2 secrets engine (dev mode l'active déjà, mais on s'assure)
vault secrets enable -path=secret kv-v2 2>/dev/null || true

# JWT secret (64 bytes base64 = ~86 chars → 512 bits of entropy)
vault kv put secret/stonks/jwt jwt_secret="$(openssl rand -base64 64)"

# AES-256-GCM key (32 bytes base64)
vault kv put secret/stonks/aes aes_key="$(openssl rand -base64 32)"

echo "✅ Vault init complete."
