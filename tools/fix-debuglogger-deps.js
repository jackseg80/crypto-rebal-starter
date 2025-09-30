#!/usr/bin/env node

/**
 * Script de réparation des dépendances debugLogger
 * Ajoute des guards de sécurité pour éviter les erreurs si debugLogger n'est pas disponible
 */

const fs = require('fs');
const path = require('path');

const replacements = [
    // Pattern pour capturer debugLogger.method(...)
    {
        pattern: /debugLogger\.(info|debug|warn|error|ui|api|perf|perfEnd)\(/g,
        replacement: '(window.debugLogger || window.console).$1(',
    },
    // Pattern pour captures plus complexes avec conditions
    {
        pattern: /debugLogger\./g,
        replacement: '(window.debugLogger || {info:console.log,debug:console.log,warn:console.warn,error:console.error,ui:console.log,api:console.log,perf:console.time,perfEnd:console.timeEnd}).',
    }
];

function fixFile(filePath) {
    try {
        let content = fs.readFileSync(filePath, 'utf8');
        let changed = false;

        // Premier remplacement : méthodes simples
        content = content.replace(/debugLogger\.(info|debug|warn|error|ui|api|perf|perfEnd)\(/g, (match, method) => {
            changed = true;
            // Mapping pour fallback console
            const methodMap = {
                info: 'log',
                debug: 'log',
                warn: 'warn',
                error: 'error',
                ui: 'log',
                api: 'log',
                perf: 'time',
                perfEnd: 'timeEnd'
            };
            return `(window.debugLogger?.${method} || console.${methodMap[method] || 'log'})(`;
        });

        if (changed) {
            fs.writeFileSync(filePath, content, 'utf8');
            console.log(`✅ Fixed ${path.basename(filePath)}`);
            return true;
        }

        return false;
    } catch (error) {
        console.error(`❌ Error fixing ${filePath}:`, error.message);
        return false;
    }
}

function findJSFiles() {
    const files = [];

    function scan(dir) {
        try {
            const entries = fs.readdirSync(dir, { withFileTypes: true });
            for (const entry of entries) {
                const fullPath = path.join(dir, entry.name);
                if (entry.isDirectory() && !entry.name.includes('archive')) {
                    scan(fullPath);
                } else if (entry.isFile() && entry.name.endsWith('.js') && !entry.name.includes('.min.') && entry.name !== 'debug-logger.js') {
                    files.push(fullPath);
                }
            }
        } catch (e) {
            // Ignorer les erreurs de permission
        }
    }

    scan('static');
    return files;
}

function main() {
    console.log('🔧 Fixing debugLogger dependencies...\n');

    const files = findJSFiles();
    let fixedCount = 0;

    for (const file of files) {
        if (fixFile(file)) {
            fixedCount++;
        }
    }

    console.log(`\n📊 Summary: Fixed ${fixedCount} files out of ${files.length} processed`);

    if (fixedCount > 0) {
        console.log('\n✅ All debugLogger dependency issues should now be resolved!');
        console.log('💡 The frontend should load properly now.');
    } else {
        console.log('\n🤔 No files needed fixing. The issue might be elsewhere.');
    }
}

if (require.main === module) {
    main();
}