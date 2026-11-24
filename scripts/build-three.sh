#!/bin/sh
# Reconstruit public/lib/three.min.js (build IIFE global THREE, les versions récentes de three.js n'ont plus de build UMD)
# usage : sh scripts/build-three.sh 0.187.0
set -e
V=${1:-0.187.0}; T=$(mktemp -d)
cd "$T" && npm init -y >/dev/null && npm i "three@$V" esbuild >/dev/null
echo "export * from 'three';" > entry.js
npx esbuild entry.js --bundle --format=iife --global-name=THREE --minify --target=es2019 --outfile=three.min.js
cd - >/dev/null && cp "$T/three.min.js" public/lib/three.min.js && echo "public/lib/three.min.js ← three@$V"
