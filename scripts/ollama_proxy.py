import asyncio
import sys

async def handle_client(reader, writer):
    try:
        remote_reader, remote_writer = await asyncio.open_connection('127.0.0.1', 11434)
    except Exception as e:
        print(f"Failed to connect to local Ollama on 127.0.0.1:11434: {e}")
        writer.close()
        return

    async def forward(src, dst):
        try:
            while True:
                data = await src.read(4096)
                if not data:
                    break
                dst.write(data)
                await dst.drain()
        except Exception:
            pass
        finally:
            try:
                dst.close()
                await dst.wait_closed()
            except Exception:
                pass

    # Start bi-directional forwarding
    asyncio.create_task(forward(reader, remote_writer))
    asyncio.create_task(forward(remote_reader, writer))

async def main():
    ips = ['172.17.0.1', '172.18.0.1']
    port = 11435
    
    servers = []
    for ip in ips:
        try:
            server = await asyncio.start_server(handle_client, ip, port)
            print(f"Listening on {ip}:{port}...")
            servers.append(server)
        except Exception as e:
            print(f"Failed to bind to {ip}:{port}: {e}")
            
    if not servers:
        print("Error: Could not start proxy on any IP interface!")
        sys.exit(1)
        
    print("Ollama TCP proxy started successfully.")
    
    tasks = [server.serve_forever() for server in servers]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down proxy...")
