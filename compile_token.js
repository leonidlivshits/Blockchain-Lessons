const fs = require("node:fs");
const path = require("node:path");
const solc = require("solc");

const root = __dirname;
const contractName = "CourseToken";
const sourceName = `${contractName}.sol`;
const source = fs.readFileSync(path.join(root, sourceName), "utf8");
const modulesRoot = path.join(root, "node_modules");

function findImports(importPath) {
  const localImportPath = importPath.replace(
    /^@openzeppelin\/contracts@5\.4\.0\//,
    "@openzeppelin/contracts/",
  );
  const importedFile = path.resolve(modulesRoot, localImportPath);
  if (!importedFile.startsWith(modulesRoot + path.sep)) {
    return { error: `Import outside node_modules: ${importPath}` };
  }
  try {
    return { contents: fs.readFileSync(importedFile, "utf8") };
  } catch {
    return { error: `Cannot read import: ${importPath}` };
  }
}

const input = {
  language: "Solidity",
  sources: { [sourceName]: { content: source } },
  settings: {
    optimizer: { enabled: true, runs: 200 },
    outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } },
  },
};
const output = JSON.parse(solc.compile(JSON.stringify(input), { import: findImports }));
for (const error of output.errors || []) {
  console.error(error.formattedMessage);
}
if (output.errors?.some((error) => error.severity === "error")) {
  process.exit(1);
}

const compiled = output.contracts[sourceName][contractName];
const artifact = {
  contractName,
  compiler: solc.version(),
  abi: compiled.abi,
  bytecode: `0x${compiled.evm.bytecode.object}`,
};
const buildDirectory = path.join(root, "build");
fs.mkdirSync(buildDirectory, { recursive: true });
const artifactPath = path.join(buildDirectory, `${contractName}.json`);
fs.writeFileSync(artifactPath, `${JSON.stringify(artifact, null, 2)}\n`);
console.log(`Compiled ${sourceName} with ${solc.version()}: ${artifactPath}`);
