"""IDB persistence, archive interoperability and explicit storage failure recovery.

Synthetic metadata fixtures exercise storage only; biological recognition is
covered by the independent observation/end-to-end browser test.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).resolve().parents[1]/'output'/'collection-validation'
out.mkdir(parents=True,exist_ok=True)
fixture=json.loads((out/'desktop-export-fixture.json').read_text(encoding='utf8'))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1366,'height':768},accept_downloads=True)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:8094/')
    page.wait_for_function('window.__menu?.ready',timeout=90000)
    result=page.evaluate("""async archive=>{
      const store=await import('./collection_store.js');
      const blob=new Blob([JSON.stringify(archive)],{type:'application/json'});
      const imported=await store.importCollection(blob),twice=await store.importCollection(blob);
      if(imported.addedPhotos!==8||twice.addedPhotos!==0)throw Error('Desktop/browser archive import mismatch');
      let collection=await store.listCollection();
      if(collection.guides[0].photoId!=='p1'||collection.results.length!==1)throw Error('Cover/result restore failed');
      const originalMetadata=JSON.stringify(collection.photos.find(p=>p.id==='p0').metadata);
      await store.setCover('coral','p0');
      collection=await store.listCollection();
      if(JSON.stringify(collection.photos.find(p=>p.id==='p0').metadata)!==originalMetadata)throw Error('Cover mutated photo metadata');
      const collision=structuredClone(archive);collision.photos[0].metadata.note='imported distinct record';
      const merged=await store.importCollection(new Blob([JSON.stringify(collision)]));
      const again=await store.importCollection(new Blob([JSON.stringify(collision)]));
      if(merged.addedPhotos!==1||again.addedPhotos!==0)throw Error('Collision merge lost/repeated distinct photo');
      const before=JSON.stringify(await store.listCollection()),invalid=structuredClone(archive);invalid.guides[0].photoId='missing';
      let rejected=false;try{await store.importCollection(new Blob([JSON.stringify(invalid)]));}catch{rejected=true;}
      if(!rejected||JSON.stringify(await store.listCollection())!==before)throw Error('Invalid import partially committed');
      const photo=await store.getPhotoBlob('p0'),put=IDBObjectStore.prototype.put;
      let fallback=false;
      IDBObjectStore.prototype.put=function(...args){if(this.name==='photos')throw new DOMException('測試用容量不足','QuotaExceededError');return put.apply(this,args);};
      try{await store.savePhoto({id:'quota-test',blob:photo,metadata:{cameraMode:'chase'}});}catch(error){fallback=error.fallback?.blob===photo;}
      finally{IDBObjectStore.prototype.put=put;}
      if(!fallback||JSON.stringify(await store.listCollection())!==before)throw Error('Quota failure lost fallback or partially committed');
      const exported=await store.exportCollection();window.__collectionArchive=await exported.text();
      return {imported,twice,collision:merged,reimport:again,invalidAtomic:true,quotaFallback:true,count:(await store.listCollection()).photos.length};
    }""",fixture)
    with page.expect_download(predicate=lambda d:d.suggested_filename.endswith('.png')) as download:
        page.get_by_role('button',name='下載原圖與拍攝資料').click()
    download.value.save_as(out/'fallback-original.png')
    assert not page.locator('.collection-save-fallback').count()
    (out/'browser-export-fixture.json').write_text(page.evaluate('window.__collectionArchive'),encoding='utf8')
    page.reload();page.wait_for_function('window.__menu?.ready',timeout=90000)
    persisted=page.evaluate("""async()=>{const store=await import('./collection_store.js');const data=await store.listCollection();return {photos:data.photos.length,cover:data.guides[0].photoId,bytes:(await store.getPhotoBlob('p0')).size};}""")
    assert persisted['photos']==9 and persisted['cover']=='p0' and persisted['bytes']>0,persisted
    # Explicit public panel API on a separate instance: navigation, cover detail,
    # records and close hooks. Existing app/menu integrations remain untouched.
    page.evaluate("""async()=>{const {installCollectionPanel}=await import('./collection_panel.js');window.__collectionHooks={open:0,close:0};window.__storagePanel=installCollectionPanel({onOpen:()=>window.__collectionHooks.open++,onClose:()=>window.__collectionHooks.close++});await window.__storagePanel.open();}""")
    panel=page.locator('.collection-panel[open]')
    assert panel.locator('.collection-locked').count()==4
    panel.get_by_role('button',name='查看珊瑚').click()
    assert panel.get_by_role('button',name='目前圖鑑封面').is_disabled()
    panel.get_by_role('button',name='← 返回收藏').click()
    panel.get_by_role('tab',name='工程紀錄').click()
    assert panel.get_by_text('水下巡檢',exact=True).is_visible()
    panel.get_by_role('tab',name='照片',exact=True).click()
    assert panel.locator('.collection-photo-button').count()==9
    panel.get_by_role('button',name='關閉收藏').click()
    assert page.evaluate('window.__collectionHooks')=={'open':1,'close':1}
    assert not errors,errors
    result.update({'reloaded':persisted,'panelHooks':True,'errors':errors})
    (out/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    browser.close()
print(json.dumps(result,ensure_ascii=False))
