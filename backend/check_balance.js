const fs = require('fs');
const html = fs.readFileSync('d:/CobraQ/CobraQ_v3.html', 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
const code = scriptMatch[1];

// Check for function definitions and call issues
const lines = code.split('\n');
let braceCount = 0, parenCount = 0, bracketCount = 0;

for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    // Count braces, parens, brackets
    for (const ch of line) {
        if (ch === '{') braceCount++;
        if (ch === '}') braceCount--;
        if (ch === '(') parenCount++;
        if (ch === ')') parenCount--;
        if (ch === '[') bracketCount++;
        if (ch === ']') bracketCount--;
    }

    // Check for obvious issues
    const stripped = line.trim();
    if (stripped === '}' || stripped === '};' || stripped === '});' || stripped === '})}') {
        // Orphaned closing brace - check context
        if (braceCount < 0) {
            console.log(`Line ${li+1}: UNEXPECTED closing brace (depth would go to ${braceCount})`);
            console.log(`  ${stripped}`);
            // Show previous lines
            for (let p = Math.max(0, li-2); p <= li; p++) {
                console.log(`  ${p+1}: ${lines[p]}`);
            }
        }
    }

    if (stripped.startsWith('else') && !stripped.startsWith('else{') && !stripped.startsWith('else ') && !stripped.includes('if')) {
        console.log(`Line ${li+1}: 'else' without braces`);
        console.log(`  ${stripped}`);
    }
}

console.log(`\nFinal balance - Braces: ${braceCount}, Parens: ${parenCount}, Brackets: ${bracketCount}`);
if (braceCount !== 0) console.log(`WARNING: Unbalanced braces!`);
if (parenCount !== 0) console.log(`WARNING: Unbalanced parentheses!`);
if (bracketCount !== 0) console.log(`WARNING: Unbalanced brackets!`);
