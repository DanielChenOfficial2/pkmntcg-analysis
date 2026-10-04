const fs = require("node:fs");
const path = require("node:path");

const webRoot = fs.realpathSync(path.resolve(__dirname, "..", "..", "website"));
const inputs = process.argv.slice(2);
const requestedPaths = inputs.length > 0 ? inputs : [webRoot];
const htmlFiles = new Set();

function isWithinRoot(root, candidate) {
  const relativePath = path.relative(root, candidate);
  return relativePath === "" ||
    (relativePath !== ".." &&
      !relativePath.startsWith(`..${path.sep}`) &&
      !path.isAbsolute(relativePath));
}

function collectHtmlFiles(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      collectHtmlFiles(entryPath);
    } else if (entry.isFile() && path.extname(entry.name).toLowerCase() === ".html") {
      htmlFiles.add(entryPath);
    }
  }
}

for (const input of requestedPaths) {
  const requestedPath = path.resolve(process.cwd(), input);
  if (!isWithinRoot(webRoot, requestedPath)) {
    throw new Error(`Path must be inside ${webRoot}: ${input}`);
  }

  const resolvedPath = fs.realpathSync(requestedPath);
  if (!isWithinRoot(webRoot, resolvedPath)) {
    throw new Error(`Resolved path must be inside ${webRoot}: ${input}`);
  }

  const stats = fs.statSync(resolvedPath);
  if (stats.isDirectory()) {
    collectHtmlFiles(resolvedPath);
  } else if (stats.isFile() && path.extname(resolvedPath).toLowerCase() === ".html") {
    htmlFiles.add(resolvedPath);
  } else {
    throw new Error(`Expected an HTML file or directory: ${input}`);
  }
}

const cdnScript =
  /<script\b(?=[^>]*\bsrc\s*=\s*(?:"https:\/\/cdn\.tailwindcss\.com(?:\/[^"]*)?"|'https:\/\/cdn\.tailwindcss\.com(?:\/[^']*)?'))[^>]*>\s*<\/script\s*>/gi;
let converted = 0;

for (const filePath of htmlFiles) {
  const original = fs.readFileSync(filePath, "utf8");
  const relativeStylesheet = path
    .relative(path.dirname(filePath), path.join(webRoot, "tailwind.css"))
    .split(path.sep)
    .join("/");
  const stylesheetLink = `<link rel="stylesheet" href="${relativeStylesheet}">`;
  const updated = original.replace(cdnScript, stylesheetLink);

  if (updated !== original) {
    fs.writeFileSync(filePath, updated, "utf8");
    converted += 1;
  }
}

if (converted > 0) {
  console.log(`Converted ${converted} of ${htmlFiles.size} HTML file(s) to local Tailwind stylesheets.`);
} else {
  console.log(`No Tailwind CDN scripts found in ${htmlFiles.size} HTML file(s).`);
}
