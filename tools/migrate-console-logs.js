#!/usr/bin/env node

/**
 * Script de migration automatique des console.log vers debugLogger
 * Usage: node tools/migrate-console-logs.js [--dry-run] [pattern]
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const DRY_RUN = process.argv.includes('--dry-run');
const PATTERN = process.argv[3] || 'static/**/*.js';

console.log(`🔄 Migration console.log → debugLogger ${DRY_RUN ? '(DRY RUN)' : ''}`);
console.log(`📁 Pattern: ${PATTERN}`);

// Mapping des remplacements selon le contexte
const replacementRules = [
    // Logs d'erreurs - garder console.error
    { pattern: /console\.error\(/g, replacement: 'console.error(', keep: true },
    { pattern: /console\.warn\(/g, replacement: 'debugLogger.warn(', category: 'warning' },

    // Logs d'info/debug selon le contexte
    { pattern: /console\.log\('📊/g, replacement: "debugLogger.info('📊", category: 'info' },
    { pattern: /console\.log\('💰/g, replacement: "debugLogger.info('💰", category: 'info' },
    { pattern: /console\.log\('📈/g, replacement: "debugLogger.info('📈", category: 'info' },
    { pattern: /console\.log\('✅/g, replacement: "debugLogger.info('✅", category: 'info' },
    { pattern: /console\.log\('⚠️/g, replacement: "debugLogger.warn('⚠️", category: 'warning' },
    { pattern: /console\.log\('❌/g, replacement: "debugLogger.error('❌", category: 'error' },
    { pattern: /console\.log\('🌐/g, replacement: "debugLogger.debug('🌐", category: 'debug' },
    { pattern: /console\.log\('🔍/g, replacement: "debugLogger.debug('🔍", category: 'debug' },
    { pattern: /console\.log\('🔄/g, replacement: "debugLogger.debug('🔄", category: 'debug' },
    { pattern: /console\.log\('🎨/g, replacement: "debugLogger.ui('🎨", category: 'ui' },

    // Logs génériques (fallback vers debug)
    { pattern: /console\.log\(/g, replacement: 'debugLogger.debug(', category: 'debug' }
];

function migrateFile(filePath) {
    try {
        let content = fs.readFileSync(filePath, 'utf8');
        let changed = false;
        let stats = { info: 0, debug: 0, warning: 0, error: 0, ui: 0, kept: 0 };

        for (const rule of replacementRules) {
            if (rule.keep) {
                const matches = content.match(rule.pattern);
                if (matches) {
                    stats.kept += matches.length;
                }
                continue;
            }

            const originalContent = content;
            content = content.replace(rule.pattern, rule.replacement);

            if (content !== originalContent) {
                const matches = originalContent.match(rule.pattern);
                if (matches) {
                    stats[rule.category] += matches.length;
                    changed = true;
                }
            }
        }

        if (changed) {
            if (!DRY_RUN) {
                fs.writeFileSync(filePath, content, 'utf8');
            }

            const totalChanges = Object.values(stats).reduce((a, b) => a + b, 0) - stats.kept;
            console.log(`✅ ${filePath}: ${totalChanges} changes`, stats);
            return stats;
        }

        return null;
    } catch (error) {
        console.error(`❌ Error processing ${filePath}:`, error.message);
        return null;
    }
}

function findJSFiles(pattern) {
    try {
        const output = execSync(`find static -name "*.js" -type f`, { encoding: 'utf8' });
        return output.trim().split('\n').filter(f => f && !f.includes('.min.') && !f.includes('archive'));
    } catch (error) {
        // Fallback pour Windows
        const files = [];
        function scan(dir) {
            try {
                const entries = fs.readdirSync(dir, { withFileTypes: true });
                for (const entry of entries) {
                    const fullPath = path.join(dir, entry.name);
                    if (entry.isDirectory() && !entry.name.includes('archive')) {
                        scan(fullPath);
                    } else if (entry.isFile() && entry.name.endsWith('.js') && !entry.name.includes('.min.')) {
                        files.push(fullPath);
                    }
                }
            } catch (e) {}
        }
        scan('static');
        return files;
    }
}

function main() {
    const files = findJSFiles(PATTERN);
    let totalStats = { info: 0, debug: 0, warning: 0, error: 0, ui: 0, kept: 0, files: 0 };

    console.log(`\n🔍 Found ${files.length} JavaScript files to process\n`);

    for (const file of files) {
        const stats = migrateFile(file);
        if (stats) {
            totalStats.files++;
            Object.keys(stats).forEach(key => {
                if (key !== 'files') totalStats[key] += stats[key];
            });
        }
    }

    console.log('\n📊 Migration Summary:');
    console.log(`Files processed: ${totalStats.files}`);
    console.log(`Info logs: ${totalStats.info}`);
    console.log(`Debug logs: ${totalStats.debug}`);
    console.log(`Warning logs: ${totalStats.warning}`);
    console.log(`Error logs: ${totalStats.error}`);
    console.log(`UI logs: ${totalStats.ui}`);
    console.log(`Kept (console.error): ${totalStats.kept}`);

    const total = totalStats.info + totalStats.debug + totalStats.warning + totalStats.error + totalStats.ui;
    console.log(`\n🎯 Total console.log migrated: ${total}`);

    if (DRY_RUN) {
        console.log('\n💡 Run without --dry-run to apply changes');
    } else {
        console.log('\n✅ Migration completed!');
    }
}

if (require.main === module) {
    main();
}