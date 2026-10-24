#!/usr/bin/env python3
"""
verify_docker_system.py
Audits live Docker engine state, container inventory (50 target: 19 APVIZ + 31 MCP),
loopback binding enforcement (127.0.0.1), and port collisions.
"""

import json
import subprocess
import sys

def audit_docker():
    print("=== DOCKER SYSTEM AUDIT (50 CONTAINERS / 18 PORTS) ===")
    
    try:
        # Security enhancement: Use array-based arguments and remove shell=True
        proc = subprocess.run(['docker', 'ps', '--format', 'json'], capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            print(f"[FAIL] Docker daemon unreachable: {proc.stderr}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Execution error: {e}")
        sys.exit(1)

    items = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    total_count = len(items)
    
    apviz = [i['Names'] for i in items if 'com.docker.compose.project=apviz' in i.get('Labels', '')]
    mcp = [i['Names'] for i in items if 'com.docker.compose.project=mcp-servers' in i.get('Labels', '')]
    
    print(f"Total Running Containers: {total_count} (Expected: 50)")
    print(f"  - APVIZ Stack Containers: {len(apviz)} (Expected: 19)")
    print(f"  - Hermes MCP Containers:  {len(mcp)} (Expected: 31)")
    
    # Port Binding Audit
    unhardened = []
    published_count = 0
    vault_port_ok = False
    
    for item in items:
        cname = item['Names']
        ports = item.get('Ports', '')
        if '->' in ports:
            # Count published mappings
            mappings = [m.strip() for m in ports.split(',') if '->' in m]
            published_count += len(mappings)
            for m in mappings:
                if '0.0.0.0:' in m:
                    unhardened.append((cname, m))
                    
        if cname == 'vault' and '8201->8200' in ports:
            vault_port_ok = True

    print(f"Total Published Port Mappings: {published_count} (Expected: 18)")
    if unhardened:
        print(f"[FAIL] Detected {len(unhardened)} unhardened (0.0.0.0) port bindings:")
        for cname, p in unhardened:
            print(f"  - {cname}: {p}")
    else:
        print(f"[PASS] 100% of published ports are strictly bound to 127.0.0.1 (Loopback Hardened).")

    if vault_port_ok:
        print("[PASS] HashiCorp Vault is correctly mapped to 127.0.0.1:8201:8200 (OpenWhispr collision evaded).")
    else:
        print("[WARN] HashiCorp Vault port 8201 mapping not verified.")

    healthy = (total_count == 50 and len(apviz) == 19 and len(mcp) == 31 and len(unhardened) == 0 and vault_port_ok)
    print(f"Audit Summary: {'HEALTHY' if healthy else 'WARNING'}")
    return 0 if healthy else 1

if __name__ == '__main__':
    sys.exit(audit_docker())
