import asyncio,json,unittest
import websockets
from rov01sim.engine import Simulator
from rov01sim.server import SimHost

class RepairNetworkTests(unittest.IsolatedAsyncioTestCase):
 async def test_three_clients_share_work_and_reconnect(self):
  host=SimHost(Simulator('cooperative_cable_repair',42))
  states=[None]*3;sessions=[None]*3;replies=[asyncio.Queue() for _ in range(3)];clients=[];tasks=[]
  async def receive(i,ws):
   async for raw in ws:
    m=json.loads(raw)
    if m['type']=='state':states[i]=m
    elif m['type']=='session':sessions[i]=m
    elif m['type']=='operation_result':await replies[i].put(m)
  async def wait(check):
   for _ in range(600):
    if check():return
    await asyncio.sleep(.025)
   self.fail('Timed out waiting for shared repair state')
  async def operation(i,verb,**extra):
   await clients[i].send(json.dumps(dict(type='operation',action='repair',verb=verb,**extra)))
   m=await asyncio.wait_for(replies[i].get(),5);self.assertTrue(m.get('ok'),m)
  async def physics():
   while True:
    for _ in range(4):host.room.step(.01)
    await asyncio.sleep(.015)
  async with websockets.serve(host.viewer_handler,'127.0.0.1',0) as server:
   url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
   try:
    for i in range(3):
     ws=await websockets.connect(url);clients.append(ws);tasks.append(asyncio.create_task(receive(i,ws)))
     await ws.send(json.dumps({'type':'join','name':f'Tech-{i}'}))
    await wait(lambda:all(sessions) and all(states))
    # Keep the integration test focused on public socket ownership and shared
    # workflow; movement/proximity are tested independently in test_repair.
    for i,p in enumerate(host.room.players.values()):host.room.vehicles[p.vehicle_id].vehicle.s.pos[:]=[7.,-i,10.8]
    async def workflow_ticks():
     from rov01sim.repair import ensure_repair
     while True:
      run=ensure_repair(host.room.primary);run.step(.1,host.room.vehicles);host.room.tick+=1
      for s in host.room.vehicles.values():s.t+=.1
      await asyncio.sleep(.015)
    tasks.append(asyncio.create_task(workflow_ticks()))
    for i,r in enumerate(('survey','service','verify')):await operation(i,'role',role=r)
    await operation(0,'start');await wait(lambda:states[2]['repair']['phase']==1)
    await operation(1,'start');await wait(lambda:states[0]['repair']['phase']==2)
    await operation(1,'start');await asyncio.sleep(.25)
    self.assertEqual(states[0]['repair']['progress'],0)
    await operation(0,'assist');await wait(lambda:states[2]['repair']['phase']==3)
    await operation(2,'start');await wait(lambda:all(s['repair']['completed'] for s in states))
    self.assertEqual(states[0]['repair']['records'],states[2]['repair']['records'])
    token=sessions[2]['resume_token'];vid=sessions[2]['vehicle_id'];await clients[2].close()
    ws=await websockets.connect(url);clients[2]=ws;sessions[2]=None;states[2]=None;tasks.append(asyncio.create_task(receive(2,ws)))
    await ws.send(json.dumps({'type':'join','resume_token':token}))
    await wait(lambda:sessions[2] and states[2])
    self.assertEqual(sessions[2]['vehicle_id'],vid);self.assertTrue(states[2]['repair']['completed'])
   finally:
    for task in tasks:task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
    for ws in clients:await ws.close()
