#!/usr/bin/env bash
# Migração para dois repos: privado (source) + público (dist).
#
# COMO USAR:
#   1) Crie o repo privado no GitHub: denerbatista/cordial-horarios-src
#      (ou outro nome — edite PRIVATE_REPO_URL abaixo)
#   2) No seu PC, dentro do clone do repo público atual, rode:
#         bash migration/migrate.sh
#   3) Siga as instruções no fim do script (deploy key, push inicial,
#      esvaziar o repo público).
#
# Este script faz:
#   - Clona o repo privado num diretório irmão (../cordial-horarios-src)
#   - Copia o source code (scripts/, fixtures/, requirements.txt, site/,
#     migration/) para lá
#   - Adapta o workflow pro repo privado
#   - Cria ssh keys (deploy key) pra você cadastrar
#   - NÃO mexe ainda no repo público — isso é manual no fim

set -euo pipefail

PRIVATE_REPO_URL="${PRIVATE_REPO_URL:-git@github.com:denerbatista/cordial-horarios-src.git}"
PUBLIC_DIR="$(pwd)"
PRIVATE_NAME="$(basename "$PRIVATE_REPO_URL" .git)"
PRIVATE_DIR="$(dirname "$PUBLIC_DIR")/$PRIVATE_NAME"

if [ ! -f site/index.html ]; then
  echo "ERRO: rode este script da raiz do repo público (cordial-horarios)" >&2
  exit 1
fi

echo "=== Migração para dois repos ==="
echo " público (dist):  $PUBLIC_DIR"
echo " privado (src):   $PRIVATE_DIR"
echo " repo privado URL: $PRIVATE_REPO_URL"
echo
read -p "Continuar? [y/N] " ok
[[ "$ok" =~ ^[yY] ]] || { echo "abortado."; exit 0; }

# 1) Clonar/preparar o repo privado
if [ -d "$PRIVATE_DIR/.git" ]; then
  echo "[ok] repo privado já clonado em $PRIVATE_DIR"
else
  echo "Clonando repo privado…"
  git clone "$PRIVATE_REPO_URL" "$PRIVATE_DIR" || {
    echo "AVISO: clone falhou. O repo privado existe e está acessível?"
    echo "Se ainda não criou, crie agora no GitHub e rode de novo."
    exit 2
  }
fi

# 2) Copiar source pro privado
echo "Copiando source…"
rsync -a --delete \
  --exclude='.git' \
  --exclude='dist' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='.github' \
  scripts/ fixtures/ migration/ "$PRIVATE_DIR/" 2>/dev/null || true

# Copia arquivos individuais
for f in requirements.txt README.md .gitignore site/index.html site/manifest.webmanifest \
         site/404.html site/robots.txt site/favicon-32.png site/icon-192.png \
         site/icon-512.png site/og-image.png site/og-image-v2.png \
         site/googleae6d8b54ec09de5a.html; do
  if [ -f "$f" ]; then
    mkdir -p "$PRIVATE_DIR/$(dirname "$f")"
    cp -p "$f" "$PRIVATE_DIR/$f"
  fi
done

# 3) Adiciona workflow do privado
mkdir -p "$PRIVATE_DIR/.github/workflows"
cp migration/private-workflow.yml "$PRIVATE_DIR/.github/workflows/build-and-deploy.yml"

# 4) Cria gitignore extra
cat >> "$PRIVATE_DIR/.gitignore" <<'EOF'

# Migração
dist/
node_modules/
*.local
EOF

# 5) Gera deploy key (se ainda não existe)
KEY_DIR="$PRIVATE_DIR/.deploy-keys"
mkdir -p "$KEY_DIR"
if [ ! -f "$KEY_DIR/id_ed25519" ]; then
  echo "Gerando deploy key…"
  ssh-keygen -t ed25519 -C "cordial-deploy-key" -f "$KEY_DIR/id_ed25519" -N ""
fi

echo
echo "================ PRÓXIMOS PASSOS (manual) ================"
echo
echo "A) Adicionar a CHAVE PÚBLICA como Deploy Key no repo PÚBLICO:"
echo "   1. Vá em https://github.com/denerbatista/cordial-horarios/settings/keys"
echo "   2. Clique 'Add deploy key', nome: 'private-build-bot'"
echo "   3. Cole o conteúdo abaixo (tudo numa linha):"
echo "----- chave pública -----"
cat "$KEY_DIR/id_ed25519.pub"
echo "-------------------------"
echo "   4. MARQUE 'Allow write access'"
echo
echo "B) Adicionar a CHAVE PRIVADA como Secret no repo PRIVADO:"
echo "   1. Vá em https://github.com/denerbatista/$PRIVATE_NAME/settings/secrets/actions"
echo "   2. Clique 'New repository secret', nome: DEPLOY_KEY"
echo "   3. Cole o conteúdo do arquivo: $KEY_DIR/id_ed25519"
echo "      (cat com: cat \"$KEY_DIR/id_ed25519\")"
echo
echo "C) Apagar a pasta .deploy-keys do disco DEPOIS de cadastrar:"
echo "   rm -rf \"$KEY_DIR\""
echo "   (a chave já está cadastrada no GitHub, não precisa local)"
echo
echo "D) Commitar e pushar no repo PRIVADO:"
echo "   cd \"$PRIVATE_DIR\""
echo "   git add ."
echo "   git commit -m 'init: migração do source para repo privado'"
echo "   git push origin main"
echo
echo "E) Registrar o self-hosted runner no repo PRIVADO:"
echo "   https://github.com/denerbatista/$PRIVATE_NAME/settings/actions/runners/new"
echo "   (etiqueta: 'cordial')"
echo
echo "F) Testar o workflow do privado (dispatch manual):"
echo "   https://github.com/denerbatista/$PRIVATE_NAME/actions/workflows/build-and-deploy.yml"
echo "   Clique 'Run workflow'. Quando ele rodar com sucesso e pushar pro público,"
echo "   prossiga pro passo G."
echo
echo "G) Esvaziar o repo PÚBLICO (manter só os artefatos):"
echo "   No clone do público (este diretório atual):"
echo "   git rm -rf scripts/ fixtures/ migration/ requirements.txt README.md \\"
echo "              .github/workflows/update-schedules.yml"
echo "   git mv site/* ."
echo "   rmdir site"
echo "   cp migration/public-workflow.yml .github/workflows/pages.yml"
echo "   git add -A"
echo "   git commit -m 'migração: público vira só dist, build movido pro repo privado'"
echo "   git push"
echo
echo "Depois disso o cordial-horarios público fica só com index.html (minificado),"
echo "schedules.json e assets. O source fica privado em $PRIVATE_NAME."
echo
echo "=============================================================="
