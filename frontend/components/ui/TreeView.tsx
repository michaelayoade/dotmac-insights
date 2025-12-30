'use client';

import { useState, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { ChevronRight, ChevronDown, Folder, FolderOpen, File } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// =============================================================================
// TREE VIEW
// =============================================================================

export interface TreeNode<T = Record<string, unknown>> {
  id: string | number;
  label: string;
  icon?: LucideIcon;
  children?: TreeNode<T>[];
  data?: T;
  disabled?: boolean;
  /** Custom class for this node */
  className?: string;
}

export interface TreeViewProps<T = Record<string, unknown>> {
  /** Tree data */
  data: TreeNode<T>[];
  /** Custom render function for node content */
  renderNode?: (node: TreeNode<T>, level: number, expanded: boolean) => React.ReactNode;
  /** Callback when a node is expanded/collapsed */
  onToggle?: (nodeId: string | number, expanded: boolean) => void;
  /** Callback when a node is selected */
  onSelect?: (node: TreeNode<T>) => void;
  /** Currently selected node ID */
  selectedId?: string | number;
  /** IDs of expanded nodes (controlled) */
  expandedIds?: Set<string | number>;
  /** IDs to expand by default (uncontrolled) */
  defaultExpandedIds?: Set<string | number>;
  /** Expand all nodes by default */
  defaultExpandAll?: boolean;
  /** Show connecting lines */
  showLines?: boolean;
  /** Show icons */
  showIcons?: boolean;
  /** Custom icons for folder/file */
  icons?: {
    expanded?: LucideIcon;
    collapsed?: LucideIcon;
    leaf?: LucideIcon;
  };
  /** Indent size per level (in pixels) */
  indentSize?: number;
  /** Loading state */
  loading?: boolean;
  /** Empty state message */
  emptyMessage?: string;
  /** Custom class name */
  className?: string;
}

export function TreeView<T = Record<string, unknown>>({
  data,
  renderNode,
  onToggle,
  onSelect,
  selectedId,
  expandedIds: controlledExpandedIds,
  defaultExpandedIds,
  defaultExpandAll = false,
  showLines = true,
  showIcons = true,
  icons,
  indentSize = 20,
  loading = false,
  emptyMessage = 'No items',
  className,
}: TreeViewProps<T>) {
  // Collect all node IDs for defaultExpandAll
  const allNodeIds = useMemo(() => {
    const ids = new Set<string | number>();
    const collect = (nodes: TreeNode<T>[]) => {
      nodes.forEach((node) => {
        if (node.children && node.children.length > 0) {
          ids.add(node.id);
          collect(node.children);
        }
      });
    };
    collect(data);
    return ids;
  }, [data]);

  // Internal expanded state
  const [internalExpandedIds, setInternalExpandedIds] = useState<Set<string | number>>(() => {
    if (defaultExpandAll) return new Set(allNodeIds);
    return defaultExpandedIds || new Set();
  });

  // Use controlled or internal state
  const expandedIds = controlledExpandedIds ?? internalExpandedIds;

  const handleToggle = useCallback(
    (nodeId: string | number) => {
      const newExpanded = !expandedIds.has(nodeId);

      if (controlledExpandedIds) {
        onToggle?.(nodeId, newExpanded);
      } else {
        setInternalExpandedIds((prev) => {
          const next = new Set(prev);
          if (newExpanded) {
            next.add(nodeId);
          } else {
            next.delete(nodeId);
          }
          return next;
        });
        onToggle?.(nodeId, newExpanded);
      }
    },
    [expandedIds, controlledExpandedIds, onToggle]
  );

  const handleSelect = useCallback(
    (node: TreeNode<T>) => {
      if (!node.disabled) {
        onSelect?.(node);
      }
    },
    [onSelect]
  );

  // Icons
  const ExpandedIcon = icons?.expanded || FolderOpen;
  const CollapsedIcon = icons?.collapsed || Folder;
  const LeafIcon = icons?.leaf || File;

  if (loading) {
    return (
      <div className={cn('space-y-2 animate-pulse', className)}>
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center gap-2" style={{ paddingLeft: (i % 3) * indentSize }}>
            <div className="w-4 h-4 bg-slate-elevated rounded" />
            <div className="h-4 w-32 bg-slate-elevated rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className={cn('text-center py-8 text-slate-muted text-sm', className)}>
        {emptyMessage}
      </div>
    );
  }

  const renderTreeNode = (node: TreeNode<T>, level: number): React.ReactNode => {
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedIds.has(node.id);
    const isSelected = selectedId === node.id;
    const NodeIcon = node.icon || (hasChildren ? (isExpanded ? ExpandedIcon : CollapsedIcon) : LeafIcon);

    return (
      <div key={node.id} className={node.className}>
        <div
          className={cn(
            'group flex items-center gap-1 py-1 px-2 rounded-md cursor-pointer transition-colors',
            isSelected
              ? 'bg-teal-electric/15 text-teal-electric'
              : 'hover:bg-slate-elevated text-foreground',
            node.disabled && 'opacity-50 cursor-not-allowed'
          )}
          style={{ paddingLeft: level * indentSize + 8 }}
          onClick={() => {
            if (hasChildren) {
              handleToggle(node.id);
            }
            handleSelect(node);
          }}
          role="treeitem"
          aria-expanded={hasChildren ? isExpanded : undefined}
          aria-selected={isSelected}
        >
          {/* Expand/Collapse Icon */}
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleToggle(node.id);
              }}
              className="p-0.5 hover:bg-slate-border rounded transition-colors"
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
            >
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-slate-muted" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-muted" />
              )}
            </button>
          ) : (
            <span className="w-5" /> // Spacer for alignment
          )}

          {/* Node Icon */}
          {showIcons && (
            <NodeIcon
              className={cn(
                'w-4 h-4 flex-shrink-0',
                isSelected ? 'text-teal-electric' : 'text-slate-muted'
              )}
            />
          )}

          {/* Node Content */}
          <div className="flex-1 min-w-0">
            {renderNode ? (
              renderNode(node, level, isExpanded)
            ) : (
              <span className="text-sm truncate">{node.label}</span>
            )}
          </div>
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div className={cn('relative', showLines && 'before:absolute before:left-[calc(theme(spacing.4)+1px)] before:top-0 before:bottom-0 before:w-px before:bg-slate-border')} style={{ marginLeft: level > 0 ? indentSize / 2 : 0 }}>
            {node.children!.map((child) => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={cn('', className)} role="tree">
      {data.map((node) => renderTreeNode(node, 0))}
    </div>
  );
}

// =============================================================================
// TREE VIEW UTILITIES
// =============================================================================

/**
 * Convert a flat list with parent references to a tree structure
 */
export function buildTree<T extends { id: string | number; parent_id?: string | number | null; name?: string; label?: string }>(
  items: T[],
  options?: {
    labelKey?: keyof T;
    parentKey?: keyof T;
    sortBy?: keyof T;
    sortOrder?: 'asc' | 'desc';
  }
): TreeNode<T>[] {
  const { labelKey = 'name', parentKey = 'parent_id', sortBy, sortOrder = 'asc' } = options || {};

  const map = new Map<string | number, TreeNode<T>>();
  const roots: TreeNode<T>[] = [];

  // Create nodes
  items.forEach((item) => {
    map.set(item.id, {
      id: item.id,
      label: String(item[labelKey] || item.label || item.name || item.id),
      data: item,
      children: [],
    });
  });

  // Build tree
  items.forEach((item) => {
    const node = map.get(item.id)!;
    const parentId = item[parentKey as keyof T] as string | number | null | undefined;

    if (parentId && map.has(parentId)) {
      map.get(parentId)!.children!.push(node);
    } else {
      roots.push(node);
    }
  });

  // Sort if requested
  if (sortBy) {
    const sorter = (a: TreeNode<T>, b: TreeNode<T>) => {
      const aVal = a.data?.[sortBy] ?? a.label;
      const bVal = b.data?.[sortBy] ?? b.label;
      const cmp = String(aVal).localeCompare(String(bVal));
      return sortOrder === 'desc' ? -cmp : cmp;
    };

    const sortTree = (nodes: TreeNode<T>[]) => {
      nodes.sort(sorter);
      nodes.forEach((node) => {
        if (node.children && node.children.length > 0) {
          sortTree(node.children);
        }
      });
    };

    sortTree(roots);
  }

  return roots;
}

/**
 * Find a node by ID in a tree
 */
export function findNode<T>(
  tree: TreeNode<T>[],
  id: string | number
): TreeNode<T> | null {
  for (const node of tree) {
    if (node.id === id) return node;
    if (node.children) {
      const found = findNode(node.children, id);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Get all ancestor IDs for a node
 */
export function getAncestorIds<T>(
  tree: TreeNode<T>[],
  targetId: string | number,
  path: (string | number)[] = []
): (string | number)[] | null {
  for (const node of tree) {
    if (node.id === targetId) return path;
    if (node.children) {
      const result = getAncestorIds(node.children, targetId, [...path, node.id]);
      if (result) return result;
    }
  }
  return null;
}

/**
 * Flatten a tree to a list
 */
export function flattenTree<T>(tree: TreeNode<T>[]): TreeNode<T>[] {
  const result: TreeNode<T>[] = [];
  const traverse = (nodes: TreeNode<T>[]) => {
    nodes.forEach((node) => {
      result.push(node);
      if (node.children) traverse(node.children);
    });
  };
  traverse(tree);
  return result;
}

export default TreeView;
