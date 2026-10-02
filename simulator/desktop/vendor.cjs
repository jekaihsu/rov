const fs=require('node:fs'),path=require('node:path');
const source=path.resolve(path.dirname(require.resolve('three')),'..');
const target=path.resolve(__dirname,'../viewer/vendor/three');
fs.mkdirSync(target,{recursive:true});
for(const sub of ['build','examples/jsm'])fs.cpSync(path.join(source,sub),path.join(target,sub),{recursive:true});
fs.copyFileSync(path.join(source,'LICENSE'),path.join(target,'LICENSE'));
console.log('Local Three.js modules ready:',target);
