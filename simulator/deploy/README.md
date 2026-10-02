# Three-player online pilot

The current release permits three players per room. Rendering runs in each
player's browser; the shared Python backend runs vehicle physics, tether dynamics,
room state and surface marks. A cloud GPU is not required for this deployment.
GPU video streaming would be a separate deployment and must be benchmarked for
three independent views, encoding latency and stream capacity.

On a Linux host with Docker Compose, point your domain to the host, allow TCP
80/443, set `ROV_DOMAIN` in the shell or a local `.env`, then run from this folder:

```sh
docker compose up -d --build
```

Open `https://YOUR-DOMAIN`, choose the same room code, and start from the main
menu. Caddy serves HTTPS and forwards `/ws` to the multiplayer service; backend
HTTP, WebSocket and SDK ports are not published directly. Keep the SDK local.

Before sharing publicly, test three simultaneous players from their real networks,
measure simulation tick duration, disconnect/rejoin behavior and bandwidth, and
configure access control and resource limits appropriate to your audience. The
current build is a small group prototype with no account system or public lobby.
There is no deployed public server, paid infrastructure or guaranteed capacity
in this repository. CPU/tether performance still needs a three-player load test
on the chosen host; GPU rental alone does not accelerate the current CPU solver.
