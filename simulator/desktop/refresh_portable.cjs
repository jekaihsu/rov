// Refresh our small app archive and static viewer without downloading Electron
// or duplicating the packaged runtime when disk space is limited.
const fs=require('node:fs');
const path=require('node:path');
async function main(){
  const asar=await import('@electron/asar');
  const root=path.resolve(__dirname,'../..');
  const resources=path.join(__dirname,'out','ROV Simulator-win32-x64','resources');
  const archive=path.join(resources,'app.asar');
  if(!fs.existsSync(archive))throw Error('Build the portable folder with Electron Forge first.');
  const stage=fs.mkdtempSync(path.join(root,'.runtime','desktop-app-'));
  asar.extractAll(archive,stage);
  for(const name of ['main.cjs','preload.cjs','collection_store.cjs','package.json'])fs.copyFileSync(path.join(__dirname,name),path.join(stage,name));
  const updated=path.join(resources,'app.updated.asar');
  await asar.createPackage(stage,updated);
  fs.renameSync(updated,archive);
  const viewer=path.join(root,'simulator','viewer');
  for(const target of [path.join(__dirname,'backend','rov-sim','_internal','viewer'),path.join(resources,'backend','rov-sim','_internal','viewer')])fs.cpSync(viewer,target,{recursive:true});
  fs.copyFileSync(path.join(__dirname,'README.md'),path.join(resources,'..','README.md'));
  console.log('Portable archive and viewer refreshed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
