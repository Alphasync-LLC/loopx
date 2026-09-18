#!/usr/bin/env node
// Parse supplied tracked source text only; never load or execute product modules.
import ts from 'typescript';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const request = JSON.parse(input);
const result = [];
for (const source of request.sources) {
  const tree = ts.createSourceFile(source.path, source.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  if (tree.parseDiagnostics.length) {
    const line = tree.getLineAndCharacterOfPosition(tree.parseDiagnostics[0].start ?? 0).line + 1;
    process.stdout.write(JSON.stringify({error: {path: source.path, line, code: "typescript_syntax"}}));
    process.exit(2);
  }
  const field = request.field;
  const returns = new Set((request.return_functions ?? []).filter(x => x.startsWith(`${source.path}::`)));
  const unwrap = node => {
    while (node && (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node))) node = node.expression;
    return node;
  };
  const values = expression => {
    const node = unwrap(expression);
    if (!node) return {values: [], unresolved: true};
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return {values: node.text ? [node.text] : [], unresolved: false};
    if (node.kind === ts.SyntaxKind.NullKeyword) return {values: [], unresolved: false};
    if (ts.isConditionalExpression(node)) {
      const left = values(node.whenTrue), right = values(node.whenFalse);
      return {values: [...new Set([...left.values, ...right.values])].sort(), unresolved: left.unresolved || right.unresolved};
    }
    return {values: [], unresolved: true};
  };
  const staticName = expression => {
    const node = unwrap(expression);
    return node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? node.text : null;
  };
  const named = node => {
    if (!node) return null;
    if (ts.isComputedPropertyName(node)) return staticName(node.expression);
    return ts.isIdentifier(node) ? node.text : staticName(node);
  };
  const target = node => ts.isIdentifier(node) ? node.text === field
    : ts.isPropertyAccessExpression(node) ? node.name.text === field
      : ts.isElementAccessExpression(node) && staticName(node.argumentExpression) === field;
  const reads = expression => {
    const node = unwrap(expression);
    if (!node) return false;
    if (target(node)) return true;
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) &&
        node.expression.text === 'String' && node.arguments.length === 1) return reads(node.arguments[0]);
    return ts.isBinaryExpression(node) &&
      [ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind) &&
      reads(node.left) && (staticName(node.right) === "" || unwrap(node.right).kind === ts.SyntaxKind.NullKeyword);
  };
  const literals = expression => {
    const node = unwrap(expression);
    if (!node) return [];
    if (ts.isArrayLiteralExpression(node)) return node.elements.flatMap(literals);
    if (ts.isNewExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'Set') {
      return (node.arguments ?? []).flatMap(literals);
    }
    return values(node).values;
  };
  if (request.mode === 'field_uses') {
    const fields = new Set(request.fields);
    const forms = new Map();
    // A computed member access may name any field, so it is the standing
    // unknown a name-keyed scan cannot resolve. It is reported apart from the
    // Python mapping-call count because the two exclusions differ: `rows[i]`
    // and `payload[key]` are one syntax here, so this is an upper bound.
    let dynamicSites = 0;
    // String literals a key position consumed. A field-named literal left over
    // is the name travelling as data -- the Python scan's `name_constant`.
    const keyed = new Set();
    const constants = [];
    const record = (key, form) => {
      if (!fields.has(key)) return;
      if (!forms.has(key)) forms.set(key, new Set());
      forms.get(key).add(form);
    };
    const markKeyed = name => {
      if (!name) return;
      keyed.add(name);
      if (ts.isComputedPropertyName(name)) keyed.add(unwrap(name.expression));
    };
    const visit = node => {
      if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) {
        const property = ts.isPropertyAccessExpression(node);
        const key = property ? node.name.text : staticName(node.argumentExpression);
        if (!property) {
          const argument = unwrap(node.argumentExpression);
          if (key === null && argument && !ts.isNumericLiteral(argument)) dynamicSites += 1;
          else if (key !== null) keyed.add(argument);
        }
        let target = node, parent = node.parent;
        while (parent && unwrap(parent) === target) { target = parent; parent = parent.parent; }
        const assignment = ts.isBinaryExpression(parent) && parent.left === target &&
          parent.operatorToken.kind >= ts.SyntaxKind.FirstAssignment &&
          parent.operatorToken.kind <= ts.SyntaxKind.LastAssignment;
        const update = (ts.isPrefixUnaryExpression(parent) || ts.isPostfixUnaryExpression(parent)) &&
          [ts.SyntaxKind.PlusPlusToken, ts.SyntaxKind.MinusMinusToken].includes(parent.operator);
        const deletion = ts.isDeleteExpression(parent);
        const prefix = property ? 'property' : 'subscript';
        if (assignment || update || deletion) record(key, `${prefix}_write`);
        if ((!assignment && !deletion) || update ||
            (assignment && parent.operatorToken.kind !== ts.SyntaxKind.EqualsToken)) {
          record(key, `${prefix}_read`);
        }
      } else if (ts.isBindingElement(node) && ts.isObjectBindingPattern(node.parent)) {
        // `const {field} = payload` and `const {field: alias} = payload` read
        // the field exactly as `payload.field` does, in a declaration or in a
        // parameter list. `propertyName` is present only when the binding
        // renames the key; otherwise the bound name is the key.
        const name = node.propertyName ?? node.name;
        markKeyed(name);
        record(named(name), 'destructured_read');
      } else if (ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node)) {
        // An object literal key is where TypeScript writes the field. The
        // Python scan counts the same construct as `dict_literal_key`, so
        // porting a dict literal to TypeScript must not shrink the surface.
        markKeyed(node.name);
        record(named(node.name), 'object_literal_key');
      } else if (ts.isPropertySignature(node) || ts.isPropertyDeclaration(node)) {
        // A declared contract surface: the type a retirement has to change.
        markKeyed(node.name);
        record(named(node.name), 'property_signature');
      } else if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
        if (fields.has(node.text)) constants.push(node);
      }
      ts.forEachChild(node, visit);
    };
    visit(tree);
    for (const node of constants) if (!keyed.has(node)) record(node.text, 'name_constant');
    result.push({path: source.path, dynamic_member_sites: dynamicSites, fields: Object.fromEntries(
      [...forms].map(([key, observed]) => [key, [...observed].sort()]),
    )});
    continue;
  }
  function walk(node, scope) {
    if (ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node)) scope = scope === '<module>' ? named(node.name) : `${scope}.${named(node.name)}`;
    else if (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
      const parent = node.parent;
      const name = ts.isVariableDeclaration(parent) || ts.isPropertyAssignment(parent) ? named(parent.name) : null;
      scope = name ? (scope === '<module>' ? name : `${scope}.${name}`) : '<anonymous>';
    }
    let expression, form;
    if (ts.isPropertyAssignment(node) && named(node.name) === field) { expression = node.initializer; form = 'object'; }
    else if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && target(node.left)) { expression = node.right; form = 'assignment'; }
    else if (ts.isVariableDeclaration(node) && named(node.name) === field && node.initializer) { expression = node.initializer; form = 'assignment'; }
    else if (ts.isReturnStatement(node) && returns.has(`${source.path}::${scope}`)) { expression = node.expression; form = 'return'; }
    if (form) {
      result.push({site: `${source.path}::${scope}`, line: tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1, form, ...values(expression)});
    }
    if (request.mode === 'literal_uses') {
      let observed = [];
      if (ts.isBinaryExpression(node) && [ts.SyntaxKind.EqualsEqualsToken,
        ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken,
        ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(node.operatorToken.kind)) {
        if (reads(node.left)) observed.push(...literals(node.right));
        if (reads(node.right)) observed.push(...literals(node.left));
      } else if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) &&
        ['includes', 'has'].includes(node.expression.name.text) && node.arguments.some(reads)) {
        observed.push(...literals(node.expression.expression));
      } else if (ts.isSwitchStatement(node) && reads(node.expression)) {
        for (const clause of node.caseBlock.clauses) if (ts.isCaseClause(clause)) observed.push(...literals(clause.expression));
      }
      if (observed.length) result.push({site: `${source.path}::${scope}`,
        line: tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1,
        form: 'dispatch', values: observed, unresolved: false});
    }
    ts.forEachChild(node, child => walk(child, scope));
  }
  walk(tree, '<module>');
}
process.stdout.write(JSON.stringify(result));
