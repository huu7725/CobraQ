const fs = require('fs');
const html = fs.readFileSync('d:/CobraQ/CobraQ_v3.html', 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
const code = scriptMatch[1];

// Count backticks
const backticks = (code.match(/`/g) || []).length;
console.log(`Backticks: ${backticks} (${backticks % 2 === 0 ? 'EVEN - OK' : 'ODD - UNCLOSED!'})`);

// Find template literals
let inTemplate = false;
let templateStart = -1;
let templateEnd = -1;

for (let i = 0; i < code.length; i++) {
    if (code[i] === '`' && (i === 0 || code[i-1] !== '\\')) {
        if (!inTemplate) {
            inTemplate = true;
            templateStart = i;
        } else {
            inTemplate = false;
            templateEnd = i;
        }
    }
}

if (inTemplate) {
    console.log(`UNCLOSED template literal at position ${templateStart}`);
    const start = Math.max(0, templateStart - 100);
    const end = Math.min(code.length, templateStart + 200);
    console.log(`Context: ...${code.substring(start, end)}...`);
} else {
    console.log('All template literals are properly closed');
}

// Check first 100 chars
console.log('\nFirst 100 chars:');
console.log(code.substring(0, 100));
