import yaml
with open("docker-compose.yml", "r") as f:
    compose = yaml.safe_load(f)

compose['services']['hardhat-node'] = {
    'image': 'node:20-alpine',
    'container_name': 'nyayavault-hardhat-node',
    'working_dir': '/blockchain',
    'volumes': [
        './blockchain:/blockchain'
    ],
    'command': 'sh -c "npm install && npx hardhat node --hostname 0.0.0.0"',
    'ports': ['8545:8545'],
    'healthcheck': {
        'test': ['CMD-SHELL', 'wget -q --header="Content-Type: application/json" --post-data=\'{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}\' -O - http://127.0.0.1:8545 || exit 1'],
        'interval': '5s',
        'timeout': '5s',
        'retries': 20
    }
}

compose['services']['contract-deploy'] = {
    'image': 'node:20-alpine',
    'container_name': 'nyayavault-contract-deploy',
    'working_dir': '/blockchain',
    'volumes': [
        './blockchain:/blockchain',
        'contract-artifacts:/artifacts'
    ],
    'environment': {
        'ARTIFACTS_DIR': '/artifacts'
    },
    'command': 'sh -c "npm install && npx hardhat run scripts/deploy.js --network docker"',
    'depends_on': {
        'hardhat-node': {
            'condition': 'service_healthy'
        }
    }
}

compose['services']['backend']['volumes'].append('contract-artifacts:/artifacts')
compose['services']['backend']['depends_on']['contract-deploy'] = {'condition': 'service_completed_successfully'}

compose['volumes']['contract-artifacts'] = None

with open("docker-compose.yml", "w") as f:
    yaml.dump(compose, f, sort_keys=False)
