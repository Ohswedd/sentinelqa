// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.
//
// VS Code entry point. Owns the Tree View, command registrations, and
// orchestration of the parser in `findings.ts`. The parser stays free
// of any `vscode` import so it can be tested headless.

import * as vscode from 'vscode';
import { spawn } from 'child_process';
import { existsSync } from 'fs';
import { join, isAbsolute, resolve as resolvePath } from 'path';
import {
  type Finding,
  type FindingsDocument,
  type Severity,
  findLatestRunDir,
  groupBySeverity,
  loadFindings,
} from './findings';

const SEVERITY_LABELS: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

const SEVERITY_ICONS: Record<Severity, string> = {
  critical: 'error',
  high: 'warning',
  medium: 'circle-filled',
  low: 'info',
  info: 'note',
};

class FindingsProvider implements vscode.TreeDataProvider<FindingsNode> {
  private readonly _emitter = new vscode.EventEmitter<FindingsNode | undefined>();
  readonly onDidChangeTreeData = this._emitter.event;

  private document: FindingsDocument | null = null;
  private projectRoot: string;

  constructor(projectRoot: string) {
    this.projectRoot = projectRoot;
  }

  setProjectRoot(root: string): void {
    this.projectRoot = root;
  }

  refresh(): void {
    const runDir = findLatestRunDir(this.projectRoot);
    this.document = runDir ? loadFindings(runDir) : null;
    this._emitter.fire(undefined);
  }

  getTreeItem(element: FindingsNode): vscode.TreeItem {
    return element.toTreeItem();
  }

  getChildren(element?: FindingsNode): FindingsNode[] {
    if (!this.document) {
      return [new MessageNode('No SentinelQA runs found. Use "Run audit" above.')];
    }
    if (!element) {
      const groups = groupBySeverity(this.document.findings);
      const result: FindingsNode[] = [];
      for (const [severity, findings] of groups) {
        if (findings.length === 0) continue;
        result.push(new SeverityNode(severity, findings));
      }
      if (result.length === 0) {
        result.push(new MessageNode('No findings on the latest run — green.'));
      }
      return result;
    }
    return element.children();
  }
}

abstract class FindingsNode {
  abstract toTreeItem(): vscode.TreeItem;
  children(): FindingsNode[] {
    return [];
  }
}

class SeverityNode extends FindingsNode {
  constructor(
    private readonly severity: Severity,
    private readonly findings: readonly Finding[],
  ) {
    super();
  }

  toTreeItem(): vscode.TreeItem {
    const item = new vscode.TreeItem(
      `${SEVERITY_LABELS[this.severity]} (${this.findings.length})`,
      vscode.TreeItemCollapsibleState.Expanded,
    );
    item.iconPath = new vscode.ThemeIcon(SEVERITY_ICONS[this.severity]);
    return item;
  }

  children(): FindingsNode[] {
    return this.findings.map((f) => new FindingNode(f));
  }
}

class FindingNode extends FindingsNode {
  constructor(readonly finding: Finding) {
    super();
  }

  toTreeItem(): vscode.TreeItem {
    const item = new vscode.TreeItem(
      this.finding.title,
      vscode.TreeItemCollapsibleState.None,
    );
    item.description = `[${this.finding.module}]`;
    item.tooltip = this.tooltip();
    if (this.finding.codeRef) {
      item.command = {
        command: 'sentinelqa.openFinding',
        title: 'Open source',
        arguments: [this.finding],
      };
    }
    item.contextValue = this.finding.fixable ? 'finding.fixable' : 'finding';
    return item;
  }

  private tooltip(): vscode.MarkdownString {
    const md = new vscode.MarkdownString();
    md.isTrusted = true;
    md.appendMarkdown(`**${this.finding.title}**\n\n`);
    md.appendMarkdown(`Module: \`${this.finding.module}\` · Severity: \`${this.finding.severity}\`\n\n`);
    if (this.finding.description) md.appendMarkdown(this.finding.description + '\n\n');
    if (this.finding.recommendation)
      md.appendMarkdown(`**Recommendation:** ${this.finding.recommendation}`);
    return md;
  }
}

class MessageNode extends FindingsNode {
  constructor(private readonly message: string) {
    super();
  }

  toTreeItem(): vscode.TreeItem {
    const item = new vscode.TreeItem(this.message);
    item.iconPath = new vscode.ThemeIcon('info');
    return item;
  }
}

function resolveProjectRoot(): string {
  const configured = vscode.workspace.getConfiguration('sentinelqa').get<string>('projectRoot');
  if (configured && configured.length > 0) {
    if (isAbsolute(configured)) return configured;
    const ws = vscode.workspace.workspaceFolders?.[0];
    if (ws) return resolvePath(ws.uri.fsPath, configured);
  }
  const ws = vscode.workspace.workspaceFolders?.[0];
  return ws ? ws.uri.fsPath : process.cwd();
}

function resolveCliCommand(): { command: string; args: readonly string[] } {
  const raw =
    vscode.workspace.getConfiguration('sentinelqa').get<string>('cliCommand') || 'sentinel';
  const parts = raw.trim().split(/\s+/);
  return { command: parts[0], args: parts.slice(1) };
}

export function activate(context: vscode.ExtensionContext): void {
  const projectRoot = resolveProjectRoot();
  const provider = new FindingsProvider(projectRoot);

  vscode.window.registerTreeDataProvider('sentinelqa.findings', provider);
  provider.refresh();

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('sentinelqa.projectRoot')) {
        provider.setProjectRoot(resolveProjectRoot());
        provider.refresh();
      }
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('sentinelqa.refreshFindings', () => provider.refresh()),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('sentinelqa.openFinding', async (finding: Finding) => {
      if (!finding?.codeRef) return;
      const abs = isAbsolute(finding.codeRef.path)
        ? finding.codeRef.path
        : join(resolveProjectRoot(), finding.codeRef.path);
      if (!existsSync(abs)) {
        vscode.window.showWarningMessage(
          `SentinelQA: code reference not found on disk — ${finding.codeRef.path}`,
        );
        return;
      }
      const doc = await vscode.workspace.openTextDocument(abs);
      const editor = await vscode.window.showTextDocument(doc);
      if (typeof finding.codeRef.line === 'number') {
        const line = Math.max(0, finding.codeRef.line - 1);
        const position = new vscode.Position(line, 0);
        editor.selection = new vscode.Selection(position, position);
        editor.revealRange(new vscode.Range(position, position));
      }
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('sentinelqa.runAudit', async () => {
      const { command, args } = resolveCliCommand();
      const root = resolveProjectRoot();
      const channel = vscode.window.createOutputChannel('SentinelQA');
      channel.show(true);
      channel.appendLine(`$ ${command} ${[...args, 'audit'].join(' ')}`);
      const child = spawn(command, [...args, 'audit'], { cwd: root });
      child.stdout.on('data', (d: Buffer) => channel.append(d.toString('utf-8')));
      child.stderr.on('data', (d: Buffer) => channel.append(d.toString('utf-8')));
      child.on('close', (code: number) => {
        channel.appendLine(`\n[exit ${code}]`);
        provider.refresh();
      });
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('sentinelqa.applyFix', async (node: FindingsNode) => {
      if (!(node instanceof FindingNode)) return;
      const { command, args } = resolveCliCommand();
      const root = resolveProjectRoot();
      const channel = vscode.window.createOutputChannel('SentinelQA');
      channel.show(true);
      channel.appendLine(`$ ${command} ${[...args, 'fix', '--apply', '--finding-id', node.finding.id].join(' ')}`);
      const child = spawn(
        command,
        [...args, 'fix', '--apply', '--finding-id', node.finding.id],
        { cwd: root },
      );
      child.stdout.on('data', (d: Buffer) => channel.append(d.toString('utf-8')));
      child.stderr.on('data', (d: Buffer) => channel.append(d.toString('utf-8')));
      child.on('close', (code: number) => {
        channel.appendLine(`\n[exit ${code}]`);
        provider.refresh();
      });
    }),
  );
}

export function deactivate(): void {
  // No teardown — VS Code disposes our subscriptions automatically.
}
