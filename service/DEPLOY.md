# Deploying the backend to an always-on VM (e.g. Oracle Cloud Always Free)

This service holds live TCP connections to the Warpath game server in
background threads (see `app/main.py`'s docstring) — it must run on a host
that never sleeps or scales to zero. A small always-free VM (Oracle Cloud,
or any similar box) works well; a serverless/scale-to-zero platform does not.

## 1. Provision the VM

Create an Always Free Ampere A1 (ARM) or AMD Micro instance running Ubuntu
22.04+, and note its public IP. Open port 8000 (or 443 if you set up TLS —
see step 5) in the VM's security list / network security group.

## 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# log out and back in for the group change to apply
```

## 3. Get the code onto the VM

```bash
git clone <your-repo-url> warpath-platform
cd warpath-platform/service
```

(If the repo isn't pushed anywhere yet, `scp -r service/ user@vm-ip:~/warpath-platform/service` works too.)

## 4. Configure secrets

```bash
cp .env.example .env
nano .env   # fill in DATABASE_URL, WARPATH_ENCRYPTION_KEY, DEV_USER_EMAIL, WARPATH_*
```

`DATABASE_URL` can keep pointing at your existing Neon database — Neon is
already reachable from anywhere, no change needed there.

## 5. Run it

```bash
docker compose up -d --build
curl http://localhost:8000/health
```

For a first end-to-end test, `NEXT_PUBLIC_API_BASE_URL` on the Vercel side
can point straight at `http://<vm-ip>:8000` — Vercel's proxy route calls it
server-to-server, so it works, but it's unencrypted in transit. For anything
beyond testing, put a reverse proxy in front with TLS:

```bash
# Caddy auto-provisions a Let's Encrypt cert if you have a domain pointed
# at the VM's IP (a free subdomain from a dynamic-DNS provider works fine
# for this — you don't need to buy one).
sudo docker run -d --name caddy --network host \
  -v caddy_data:/data \
  caddy caddy reverse-proxy --from your-domain.example.com --to localhost:8000
```

Then set `NEXT_PUBLIC_API_BASE_URL=https://your-domain.example.com` on Vercel.

## 6. Keep it running across reboots

`restart: unless-stopped` in `docker-compose.yml` already brings the
container back up after a Docker/VM restart — no extra step needed.

## Migrations

Run once after the first deploy (and after any future migration):

```bash
docker compose run --rm backend python -m alembic upgrade head
```
