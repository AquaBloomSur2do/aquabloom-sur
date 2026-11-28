import { access, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const examplesDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(examplesDirectory, "../..");
const manifestPath = path.join(
  examplesDirectory,
  "manifiesto-evidencia-piloto.ejemplo.json",
);
const markdownPaths = [
  "README.md",
  "docs/dataset-versioning.md",
  "docs/pilot-estimation-guide.md",
  "docs/manifiesto-evidencia-piloto.md",
];
const checkedPaths = [
  ...markdownPaths,
  "docs/examples/manifiesto-evidencia-piloto.ejemplo.json",
  "docs/examples/validate_pilot_evidence_manifest.mjs",
];
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const checksumPattern = /^[0-9a-f]{64}$/i;

function requireCondition(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function requireObject(value, label) {
  requireCondition(
    value !== null && typeof value === "object" && !Array.isArray(value),
    `${label} debe ser un objeto JSON.`,
  );
}

function requireKeys(value, keys, label) {
  for (const key of keys) {
    requireCondition(
      Object.hasOwn(value, key),
      `Falta el campo obligatorio ${label}.${key}.`,
    );
  }
}

function requireUuid(value, label) {
  requireCondition(
    typeof value === "string" && uuidPattern.test(value),
    `${label} debe ser un UUID canonico no vacio.`,
  );
}

function requireText(value, label) {
  requireCondition(
    typeof value === "string" && value.trim().length > 0,
    `${label} debe ser un texto no vacio.`,
  );
}

function validateManifest(manifest) {
  requireObject(manifest, "manifest");
  requireKeys(
    manifest,
    ["manifest_version", "synthetic", "dataset", "scene", "model", "execution"],
    "manifest",
  );
  requireCondition(manifest.manifest_version === "1.0", "Version no soportada.");
  requireCondition(manifest.synthetic === true, "El manifiesto debe ser sintetico.");

  const { dataset, scene, model, execution } = manifest;
  for (const [entity, label] of [
    [dataset, "dataset"],
    [scene, "scene"],
    [model, "model"],
    [execution, "execution"],
  ]) {
    requireObject(entity, label);
    requireCondition(entity.synthetic === true, `${label} debe ser sintetica.`);
  }

  requireKeys(
    dataset,
    ["dataset_id", "dataset_version_id", "version_number", "manifest_checksum"],
    "dataset",
  );
  requireUuid(dataset.dataset_id, "dataset.dataset_id");
  requireUuid(dataset.dataset_version_id, "dataset.dataset_version_id");
  requireCondition(
    Number.isInteger(dataset.version_number) && dataset.version_number > 0,
    "dataset.version_number debe ser un entero positivo.",
  );
  requireCondition(
    typeof dataset.manifest_checksum === "string" &&
      checksumPattern.test(dataset.manifest_checksum),
    "dataset.manifest_checksum debe ser un SHA-256 hexadecimal de 64 caracteres.",
  );

  requireKeys(
    scene,
    ["scene_id", "lake_id", "scene_identifier", "acquisition_date"],
    "scene",
  );
  requireUuid(scene.scene_id, "scene.scene_id");
  requireUuid(scene.lake_id, "scene.lake_id");
  requireText(scene.scene_identifier, "scene.scene_identifier");
  requireCondition(
    /^\d{4}-\d{2}-\d{2}$/.test(scene.acquisition_date) &&
      !Number.isNaN(Date.parse(`${scene.acquisition_date}T00:00:00Z`)) &&
      new Date(`${scene.acquisition_date}T00:00:00Z`)
        .toISOString()
        .startsWith(`${scene.acquisition_date}T`),
    "scene.acquisition_date debe usar YYYY-MM-DD.",
  );

  requireKeys(
    model,
    ["model_version_id", "training_job_id", "algorithm", "dataset_version_id"],
    "model",
  );
  requireUuid(model.model_version_id, "model.model_version_id");
  requireUuid(model.training_job_id, "model.training_job_id");
  requireUuid(model.dataset_version_id, "model.dataset_version_id");
  requireText(model.algorithm, "model.algorithm");
  requireCondition(
    model.dataset_version_id === dataset.dataset_version_id,
    "El modelo debe referenciar la version declarada del dataset.",
  );

  requireKeys(
    execution,
    ["job_id", "organization_id", "job_type", "status", "created_at", "references"],
    "execution",
  );
  requireUuid(execution.job_id, "execution.job_id");
  requireUuid(execution.organization_id, "execution.organization_id");
  requireCondition(
    ["training", "modeling", "estimation"].includes(execution.job_type),
    "execution.job_type no coincide con los tipos de trabajo del contrato.",
  );
  requireCondition(
    ["queued", "running", "completed", "failed"].includes(execution.status),
    "execution.status no coincide con los estados persistidos del trabajo.",
  );
  requireCondition(
    typeof execution.created_at === "string" &&
      /^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(execution.created_at) &&
      !Number.isNaN(Date.parse(execution.created_at)),
    "execution.created_at debe ser una fecha ISO 8601.",
  );
  requireObject(execution.references, "execution.references");
  requireKeys(
    execution.references,
    [
      "dataset_id",
      "dataset_version_id",
      "scene_id",
      "model_version_id",
      "training_job_id",
    ],
    "execution.references",
  );

  const expectedReferences = {
    dataset_id: dataset.dataset_id,
    dataset_version_id: dataset.dataset_version_id,
    scene_id: scene.scene_id,
    model_version_id: model.model_version_id,
    training_job_id: model.training_job_id,
  };
  for (const [key, expected] of Object.entries(expectedReferences)) {
    requireUuid(execution.references[key], `execution.references.${key}`);
    requireCondition(
      execution.references[key] === expected,
      `execution.references.${key} no coincide con la entidad declarada.`,
    );
  }
}

async function validateMarkdownJsonBlocks(relativePath) {
  const markdown = await readFile(path.join(repositoryRoot, relativePath), "utf8");
  const jsonBlocks = [...markdown.matchAll(/```json[ \t]*\r?\n([\s\S]*?)```/gi)];
  for (const [index, match] of jsonBlocks.entries()) {
    try {
      JSON.parse(match[1]);
    } catch (error) {
      throw new Error(
        `${relativePath}: bloque JSON ${index + 1} invalido: ${error.message}`,
      );
    }
  }
  return jsonBlocks.length;
}

async function validateLinksAndWhitespace() {
  for (const relativePath of checkedPaths) {
    const absolutePath = path.join(repositoryRoot, relativePath);
    const content = await readFile(absolutePath, "utf8");
    const lines = content.split(/\r?\n/);
    for (const [index, line] of lines.entries()) {
      requireCondition(
        !/[ \t]+$/.test(line),
        `${relativePath}:${index + 1} tiene espacios o tabs al final.`,
      );
    }

    if (!relativePath.endsWith(".md")) {
      continue;
    }
    const links = [...content.matchAll(/\[[^\]]+\]\((?<target>[^)]+)\)/g)];
    for (const match of links) {
      const target = match.groups.target.split("#", 1)[0];
      if (!target || /^(https?:\/\/|mailto:|#)/i.test(target)) {
        continue;
      }
      const linkedPath = path.resolve(path.dirname(absolutePath), target);
      try {
        await access(linkedPath);
      } catch {
        throw new Error(`${relativePath} contiene un enlace roto: ${target}`);
      }
    }
  }
}

try {
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  validateManifest(manifest);

  let markdownBlockCount = 0;
  for (const markdownPath of markdownPaths) {
    markdownBlockCount += await validateMarkdownJsonBlocks(markdownPath);
  }
  await validateLinksAndWhitespace();

  console.log(
    `OK: manifiesto valido; 4 entidades con UUID estables; ${markdownBlockCount} bloques JSON de Markdown validos; enlaces relativos y whitespace correctos.`,
  );
} catch (error) {
  console.error(`ERROR: ${error.message}`);
  process.exitCode = 1;
}
