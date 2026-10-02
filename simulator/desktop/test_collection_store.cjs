const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const {CollectionStore,LIMITS}=require('./collection_store.cjs');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6hXcAAAAASUVORK5CYII=','base64');
const image=(suffix='')=>({mime:'image/png',data:Buffer.concat([png,Buffer.from(suffix)]).toString('base64')});
const photo=(id,category=null,suffix='')=>({id,createdAt:'2026-10-02T10:00:00.000Z',metadata:{cameraMode:category?'onboard':'chase',scenario:'coral_reef',model:'falcon'},observation:category?{category,entity_id:'entity-1'}:null,image:image(suffix)});
(async()=>{
 const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'rov-collection-test-'));
 try{
  const store=new CollectionStore(path.join(temporary,'a'));
  await Promise.all(Array.from({length:8},(_,i)=>store.savePhoto(photo(`p${i}`,i<2?'coral':null,String(i)))));
  await store.saveResult({id:'mission-1',createdAt:'2026-10-02T10:00:00.000Z',title:'水下巡檢',rating:'精準完成'});
  let list=await store.list();assert.equal(list.photos.length,8);assert.equal(list.guides.length,1);
  await store.setCover({category:'coral',photoId:'p1'});
  const originalMetadata=list.photos[0].metadata;
  assert.deepEqual((await store.list()).photos[0].metadata,originalMetadata);
  await assert.rejects(store.setCover({category:'coral',photoId:'p2'}));
  await assert.rejects(store.savePhoto({...photo('illegal','seastar'),metadata:{cameraMode:'chase'}}));
  await assert.rejects(store.savePhoto(photo('../../outside')));
  await assert.rejects(store.readPhoto('../index.json'));
  await assert.rejects(store.savePhoto({...photo('large'),image:{mime:'image/png',data:'A'.repeat(Math.ceil(LIMITS.image/3)*4+4)}}));
  const archive=await store.export();
  assert.equal((await store.import(archive)).addedPhotos,0);
  const restored=new CollectionStore(path.join(temporary,'b'));
  assert.equal((await restored.import(archive)).addedPhotos,8);
  assert.equal((await restored.list()).guides[0].photoId,'p1');
  const reopened=new CollectionStore(path.join(temporary,'b'));
  assert.deepEqual(await reopened.readPhoto('p1'),image('1'));
  assert.equal((await reopened.list()).results.length,1);
  const conflicting=photo('p0','coral','different');const copy=await store.savePhoto(conflicting);
  assert.notEqual(copy.id,'p0');assert.deepEqual(await store.readPhoto('p0'),image('0'));
  const before=await store.list(),invalid=JSON.parse(JSON.stringify(archive));invalid.photos[0].id='new-photo';invalid.guides[0].photoId='missing';
  await assert.rejects(store.import(invalid));assert.deepEqual(await store.list(),before);
  await assert.rejects(store.import({...archive,version:999}));
  const rename=fs.rename;
  fs.rename=async(from,to)=>{if(to.endsWith('index.json'))throw Error('injected disk failure');return rename(from,to);};
  try{await assert.rejects(store.savePhoto(photo('failed',null,'unique-failure')),/injected/);}finally{fs.rename=rename;}
  assert.deepEqual(await store.list(),before);
  await store.savePhoto(photo('after-failure',null,'after'));assert.equal((await store.list()).photos.length,before.photos.length+1);
  const output=path.resolve(__dirname,'../output/collection-validation');await fs.mkdir(output,{recursive:true});
  await fs.writeFile(path.join(output,'desktop-export-fixture.json'),JSON.stringify(archive));
  await fs.writeFile(path.join(output,'node-results.json'),JSON.stringify({serializedWrites:8,persistentReopen:true,coverRestored:true,collisionPreservesBoth:true,invalidImportAtomic:true,diskFailureAtomic:true,pathTraversalRejected:true,thirdPersonUnlockRejected:true},null,2));
  console.log('Collection storage passed: serialized writes, reopen, covers, export/import, collisions, validation and failed-write rollback.');
 }finally{
  // Remove only the directory returned by mkdtemp beneath the explicit temp root.
  const root=path.resolve(os.tmpdir()),target=path.resolve(temporary),relative=path.relative(root,target);
  assert.ok(relative&&!relative.startsWith('..')&&!path.isAbsolute(relative)&&path.basename(target).startsWith('rov-collection-test-'));
  await fs.rm(target,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
