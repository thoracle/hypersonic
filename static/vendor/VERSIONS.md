# Vendored frontend libraries

Pinned by committed file — there is no CDN, bundler, or npm dependency at runtime.
Changing a version here means replacing the committed file, and only as an explicit
operator-requested task.

| File | Library | Version |
| --- | --- | --- |
| `three.module.js` | [Three.js](https://github.com/mrdoob/three.js) | r170 (`REVISION = '170'`) |
| `postprocessing/*.js` | Three.js `examples/jsm` postprocessing chain (EffectComposer, RenderPass, ShaderPass, MaskPass, Pass, UnrealBloomPass, CopyShader, LuminosityHighPassShader) | r170, imports rewritten to same-origin `/static/vendor/three.module.js` |
