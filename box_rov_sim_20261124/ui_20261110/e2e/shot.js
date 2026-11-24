const {chromium}=require('playwright');
(async()=>{
 const out=process.argv[2]||'base.png';
 const b=await chromium.launch({args:['--use-gl=swiftshader','--enable-webgl','--ignore-gpu-blocklist']});
 const pg=await b.newPage({viewport:{width:1600,height:900}});
 pg.on('pageerror',e=>console.log('PAGEERR',e.message));
 await pg.goto('http://127.0.0.1:28080/index.html?play=1&ws=ws://127.0.0.1:28765&model=rov01&nointro=1');
 await pg.waitForTimeout(6000);
 await pg.screenshot({path:out});
 await b.close();
})();
