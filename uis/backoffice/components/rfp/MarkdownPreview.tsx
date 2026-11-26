'use client';

import React from 'react';

/**
 * Props for the MarkdownPreview component.
 */
export interface MarkdownPreviewProps {
  /** Raw Markdown text to render as formatted JSX elements. */
  content: string;
  /** Optional fallback text when content is empty or whitespace-only. */
  emptyText?: string;
}

/**
 * Renders inline Markdown tokens (`**bold**`, `*italic*`, `` `code` ``, `[label](url)`)
 * as safe React nodes without `dangerouslySetInnerHTML`.
 *
 * @param text - Single-line or inline Markdown string.
 * @param keyPrefix - Unique React key prefix for generated inline elements.
 * @returns Array of React nodes representing the formatted inline text.
 */
function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const tokenRegex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g;
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null = tokenRegex.exec(text);
  let tokenIdx = 0;

  while (match !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];
    const key = `${keyPrefix}-${tokenIdx++}`;

    if (token.startsWith('**') && token.endsWith('**')) {
      nodes.push(
        <strong key={key} className="font-semibold text-slate-100">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      nodes.push(
        <em key={key} className="italic text-slate-200">
          {token.slice(1, -1)}
        </em>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      nodes.push(
        <code
          key={key}
          className="px-1 py-0.5 rounded bg-slate-800 text-emerald-300 font-mono text-[11px]"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('[')) {
      const linkMatch = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/.exec(token);
      if (linkMatch && linkMatch[1] && linkMatch[2]) {
        nodes.push(
          <a
            key={key}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-emerald-400 underline hover:text-emerald-300"
          >
            {linkMatch[1]}
          </a>
        );
      } else {
        nodes.push(token);
      }
    }

    lastIndex = match.index + token.length;
    match = tokenRegex.exec(text);
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

function isTableSeparator(line: string): boolean {
  return /^\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?$/.test(line.trim());
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());
}

/**
 * Lightweight, XSS-safe Markdown preview renderer for RFP department drafts
 * and consolidated proposal sections.
 *
 * @param props - Component props containing Markdown content and optional empty fallback.
 * @returns JSX Element rendering formatted headings, lists, tables, blockquotes, and inline styles.
 */
export function MarkdownPreview({
  content,
  emptyText = 'Sin contenido generado.',
}: MarkdownPreviewProps): React.ReactElement {
  const trimmed = content.trim();
  if (!trimmed) {
    return <p className="text-xs text-slate-400 italic">{emptyText}</p>;
  }

  const lines = trimmed.split(/\r?\n/);
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let blockIdx = 0;

  while (i < lines.length) {
    const line = lines[i] ?? '';
    const trimmedLine = line.trim();

    if (!trimmedLine) {
      i++;
      continue;
    }

    // Horizontal rule
    if (/^(-{3,}|\*{3,})$/.test(trimmedLine)) {
      blocks.push(<hr key={`hr-${blockIdx++}`} className="border-slate-800 my-2" />);
      i++;
      continue;
    }

    // Headings (# .. ####)
    const headingMatch = /^(#{1,4})\s+(.+)$/.exec(trimmedLine);
    if (headingMatch && headingMatch[1] && headingMatch[2]) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const key = `h-${blockIdx++}`;
      const cls =
        level === 1
          ? 'text-sm font-bold text-slate-100 mt-2 mb-1'
          : level === 2
            ? 'text-xs font-bold text-emerald-300 uppercase tracking-wide mt-2 mb-1'
            : 'text-xs font-semibold text-slate-200 mt-1.5 mb-0.5';
      blocks.push(
        <div key={key} className={cls}>
          {renderInline(text, key)}
        </div>
      );
      i++;
      continue;
    }

    // Markdown table
    if (
      trimmedLine.includes('|') &&
      i + 1 < lines.length &&
      isTableSeparator(lines[i + 1] ?? '')
    ) {
      const headers = splitTableRow(trimmedLine);
      i += 2; // Skip header + separator
      const rows: string[][] = [];
      while (i < lines.length && (lines[i] ?? '').trim().includes('|')) {
        rows.push(splitTableRow(lines[i] ?? ''));
        i++;
      }
      const key = `tbl-${blockIdx++}`;
      blocks.push(
        <div key={key} className="overflow-x-auto my-2">
          <table className="w-full text-left border-collapse text-[11px]">
            <thead>
              <tr className="border-b border-slate-700 text-slate-200">
                {headers.map((h, hIdx) => (
                  <th key={`${key}-h-${hIdx}`} className="py-1.5 px-2 font-semibold">
                    {renderInline(h, `${key}-h-${hIdx}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 text-slate-300">
              {rows.map((row, rIdx) => (
                <tr key={`${key}-r-${rIdx}`}>
                  {headers.map((_, cIdx) => (
                    <td key={`${key}-r-${rIdx}-c-${cIdx}`} className="py-1 px-2">
                      {renderInline(row[cIdx] ?? '', `${key}-r-${rIdx}-c-${cIdx}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Blockquote
    if (trimmedLine.startsWith('>')) {
      const quoteLines: string[] = [];
      while (i < lines.length && (lines[i] ?? '').trim().startsWith('>')) {
        quoteLines.push((lines[i] ?? '').trim().replace(/^>\s?/, ''));
        i++;
      }
      const key = `bq-${blockIdx++}`;
      blocks.push(
        <blockquote
          key={key}
          className="border-l-2 border-emerald-500/50 pl-3 py-0.5 text-xs text-slate-300 italic my-1.5"
        >
          {renderInline(quoteLines.join(' '), key)}
        </blockquote>
      );
      continue;
    }

    // Unordered list
    if (/^[-*]\s+/.test(trimmedLine)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test((lines[i] ?? '').trim())) {
        items.push((lines[i] ?? '').trim().replace(/^[-*]\s+/, ''));
        i++;
      }
      const key = `ul-${blockIdx++}`;
      blocks.push(
        <ul key={key} className="list-disc list-inside space-y-1 text-xs text-slate-300 pl-1">
          {items.map((item, idx) => (
            <li key={`${key}-${idx}`} className="leading-relaxed">
              {renderInline(item, `${key}-${idx}`)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Ordered list
    if (/^\d+\.\s+/.test(trimmedLine)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test((lines[i] ?? '').trim())) {
        items.push((lines[i] ?? '').trim().replace(/^\d+\.\s+/, ''));
        i++;
      }
      const key = `ol-${blockIdx++}`;
      blocks.push(
        <ol key={key} className="list-decimal list-inside space-y-1 text-xs text-slate-300 pl-1">
          {items.map((item, idx) => (
            <li key={`${key}-${idx}`} className="leading-relaxed">
              {renderInline(item, `${key}-${idx}`)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // Paragraph (collect contiguous plain lines)
    const paraLines: string[] = [];
    while (i < lines.length) {
      const cur = (lines[i] ?? '').trim();
      if (
        !cur ||
        /^(#{1,4}\s+|[-*]\s+|\d+\.\s+|>\s?|(-{3,}|\*{3,})$)/.test(cur) ||
        (cur.includes('|') && i + 1 < lines.length && isTableSeparator(lines[i + 1] ?? ''))
      ) {
        break;
      }
      paraLines.push(cur);
      i++;
    }
    const key = `p-${blockIdx++}`;
    blocks.push(
      <p key={key} className="text-xs text-slate-300 leading-relaxed">
        {renderInline(paraLines.join(' '), key)}
      </p>
    );
  }

  return <div className="space-y-2">{blocks}</div>;
}
