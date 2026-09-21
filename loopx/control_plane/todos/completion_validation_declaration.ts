import type {JsonObject} from "../effect_program.ts";

export interface TodoCompletionValidationDeclaration extends JsonObject {
  readonly validation_command: string | null;
  readonly validation_command_argv: readonly string[] | null;
  readonly validation_label: string | null;
  readonly validation_timeout_seconds: number | null;
}

export type TodoCompletionValidationDeclarationResult =
  | {readonly ok: true; readonly value: TodoCompletionValidationDeclaration}
  | {readonly ok: false; readonly summary: string};

const FIELDS = [
  "validation_command",
  "validation_command_argv",
  "validation_label",
  "validation_timeout_seconds",
] as const;

const compactString = (value: unknown): string | null => {
  if (typeof value !== "string") return null;
  const compact = value.trim();
  return compact === "" ? null : compact;
};

const validationTimeoutSeconds = (
  value: unknown,
): {ok: true; value: number | null} | {ok: false; summary: string} => {
  if (value === null || value === undefined || value === "") {
    return {ok: true, value: null};
  }
  if (
    typeof value === "number" && Number.isInteger(value) &&
    Number.isSafeInteger(value) && value >= 1 && value <= 29
  ) {
    return {ok: true, value};
  }
  if (typeof value === "string" && /^[0-9]+$/u.test(value.trim())) {
    const parsed = Number(value.trim());
    if (parsed >= 1 && parsed <= 29) return {ok: true, value: parsed};
  }
  return {
    ok: false,
    summary: "validation_timeout_seconds must be an integer between 1 and 29",
  };
};

const validationArgv = (
  value: unknown,
): {ok: true; value: readonly string[] | null} | {ok: false; summary: string} => {
  if (value === null || value === undefined || value === "") {
    return {ok: true, value: null};
  }
  let parsed: unknown = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return {
        ok: false,
        summary: "validation_command_argv must be a non-empty string array",
      };
    }
  }
  if (
    Array.isArray(parsed) && parsed.length > 0 &&
    parsed.every((item) => typeof item === "string" && item.length > 0)
  ) {
    return {ok: true, value: [...parsed]};
  }
  return {
    ok: false,
    summary: "validation_command_argv must be a non-empty string array",
  };
};

export function normalizeTodoCompletionValidationDeclaration(
  value: JsonObject,
  options: {
    readonly strict_fields?: boolean;
    readonly require_command?: boolean;
  } = {},
): TodoCompletionValidationDeclarationResult {
  if (
    options.strict_fields === true &&
    Object.keys(value).some(
      (field) => !FIELDS.includes(field as (typeof FIELDS)[number]),
    )
  ) {
    return {
      ok: false,
      summary: "completion validation declaration has unsupported fields",
    };
  }
  const label = value.validation_label;
  if (
    label !== null && label !== undefined && label !== "" &&
    typeof label !== "string"
  ) {
    return {ok: false, summary: "validation_label must be a string or null"};
  }
  const validationLabel = typeof label === "string" && label !== "" ? label : null;
  const commandRaw = value.validation_command;
  if (
    commandRaw !== null && commandRaw !== undefined &&
    typeof commandRaw !== "string"
  ) {
    return {
      ok: false,
      summary: "validation_command must be a non-empty string when declared",
    };
  }
  const validationCommand = compactString(commandRaw);
  const argv = validationArgv(value.validation_command_argv);
  if (!argv.ok) return argv;
  if (validationCommand !== null && argv.value !== null) {
    return {
      ok: false,
      summary: "validation_command and validation_command_argv are mutually exclusive",
    };
  }
  const timeout = validationTimeoutSeconds(value.validation_timeout_seconds);
  if (!timeout.ok) return timeout;
  if (validationCommand === null && argv.value === null) {
    if (timeout.value !== null) {
      return {
        ok: false,
        summary: "validation_timeout_seconds requires a validation command declaration",
      };
    }
    if (options.require_command === true) {
      return {
        ok: false,
        summary: "completion validation declaration requires a validation command",
      };
    }
  }
  return {
    ok: true,
    value: {
      validation_command: validationCommand,
      validation_command_argv: argv.value,
      validation_label: validationLabel,
      validation_timeout_seconds: timeout.value,
    },
  };
}
