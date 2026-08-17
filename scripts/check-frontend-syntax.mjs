import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import vm from "node:vm";

const root = path.resolve(process.argv[2] ?? process.cwd());
const resources = path.join(
  root,
  "myai-java-service",
  "src",
  "main",
  "resources",
);
const staticJsRoot = path.join(resources, "static", "js");
const templatesRoot = path.join(resources, "templates");

function walkFiles(directory, predicate) {
  if (!fs.existsSync(directory)) {
    return [];
  }

  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(fullPath, predicate));
    } else if (entry.isFile() && predicate(fullPath)) {
      files.push(fullPath);
    }
  }
  return files.sort((left, right) => left.localeCompare(right));
}

function displayPath(file) {
  return path.relative(root, file).split(path.sep).join("/");
}

function compile(source, filename) {
  new vm.Script(source.replace(/^\uFEFF/, ""), { filename });
}

const failures = [];
let externalScriptCount = 0;
let inlineScriptCount = 0;
let orderedBundleCount = 0;

for (const file of walkFiles(staticJsRoot, (candidate) => candidate.endsWith(".js"))) {
  try {
    compile(fs.readFileSync(file, "utf8"), displayPath(file));
    externalScriptCount += 1;
  } catch (error) {
    failures.push(`${displayPath(file)}: ${error.message}`);
  }
}

const scriptPattern = /<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi;
for (const template of walkFiles(templatesRoot, (candidate) => candidate.endsWith(".html"))) {
  const html = fs.readFileSync(template, "utf8");
  const orderedClassicSources = [];
  let match;
  let scriptIndex = 0;
  while ((match = scriptPattern.exec(html)) !== null) {
    scriptIndex += 1;
    const attributes = match[1];
    const source = match[2];
    const sourceMatch = attributes.match(/(?:^|\s)src\s*=\s*["']([^"']+)["']/i);
    if (sourceMatch) {
      const sourceReference = sourceMatch[1];
      if (!/^(?:https?:)?\/\//i.test(sourceReference)) {
        const externalPath = path.join(
          resources,
          "static",
          sourceReference.replace(/^\/+/, ""),
        );
        if (!fs.existsSync(externalPath)) {
          failures.push(
            `${displayPath(template)}: referenced script is missing: ${sourceReference}`,
          );
        } else {
          orderedClassicSources.push({
            filename: displayPath(externalPath),
            source: fs.readFileSync(externalPath, "utf8"),
          });
        }
      }
      continue;
    }
    if (source.trim().length === 0) {
      continue;
    }

    const typeMatch = attributes.match(/\btype\s*=\s*["']([^"']+)["']/i);
    if (
      typeMatch &&
      ![
        "text/javascript",
        "application/javascript",
        "module",
      ].includes(typeMatch[1].toLowerCase())
    ) {
      continue;
    }

    const filename = `${displayPath(template)}#inline-script-${scriptIndex}`;
    try {
      compile(source, filename);
      inlineScriptCount += 1;
      if (!typeMatch || typeMatch[1].toLowerCase() !== "module") {
        orderedClassicSources.push({ filename, source });
      }
    } catch (error) {
      failures.push(`${filename}: ${error.message}`);
    }
  }

  if (orderedClassicSources.length > 1) {
    const bundle = orderedClassicSources
      .map(({ filename, source }) => `/* ${filename} */\n${source}`)
      .join("\n;\n");
    try {
      compile(bundle, `${displayPath(template)}#ordered-classic-scripts`);
      orderedBundleCount += 1;
    } catch (error) {
      failures.push(
        `${displayPath(template)}: classic script ordering/global declaration conflict: ${error.message}`,
      );
    }
  }
}

if (failures.length > 0) {
  console.error("Frontend syntax validation failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exitCode = 1;
} else {
  console.log(
    `Frontend syntax: ok (${externalScriptCount} external, ${inlineScriptCount} inline, ${orderedBundleCount} ordered bundles)`,
  );
}
