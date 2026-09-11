const fs = require("fs");
const path = require("path");

async function main() {
  const DocumentRegistry = await ethers.getContractFactory("DocumentRegistry");
  const registry = await DocumentRegistry.deploy();
  await registry.waitForDeployment();
  const address = await registry.getAddress();

  console.log("DocumentRegistry deployed to:", address);

  const outDir = process.env.ARTIFACTS_DIR || path.join(__dirname, "..", "deploy_artifacts");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const contractArtifact = artifacts.readArtifactSync("DocumentRegistry");
  
  const data = {
    address: address,
    abi: contractArtifact.abi
  };

  fs.writeFileSync(
    path.join(outDir, "contract.json"),
    JSON.stringify(data, null, 2)
  );
  console.log(`Wrote contract.json to ${outDir}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
