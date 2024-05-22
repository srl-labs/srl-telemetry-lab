1. Install Docker
```bash
chmod +x docker-install.sh
./docker-install.sh
```

2. Install Containerlab
```bash
chmod +x containerlab-install.sh
./containerlab-install.sh
```

3. Update the stack.env and token.env for Alloy in configs/alloy

4. RUN
```bash
sudo containerlab deploy --reconfigure
sudo bash traffic.sh start all
```