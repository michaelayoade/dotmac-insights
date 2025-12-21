"use client";

import { useState } from "react";
import {
  Layers,
  Plus,
  RefreshCw,
  Edit,
  Trash2,
  Settings,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAssetCategories, useAssetCategoryMutations } from "@/hooks/useApi";
import type { AssetCategory } from "@/lib/api";

export default function AssetCategoriesPage() {
  const [expandedCategories, setExpandedCategories] = useState<Set<number>>(new Set());
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newCategory, setNewCategory] = useState({
    asset_category_name: "",
    enable_cwip_accounting: false,
  });

  const { data, isLoading, mutate } = useAssetCategories();
  const { create: createCategory } = useAssetCategoryMutations();

  const categories: AssetCategory[] = data?.categories ?? [];

  const toggleExpand = (id: number) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCategory.asset_category_name.trim()) return;

    try {
      await createCategory(newCategory);
      setNewCategory({ asset_category_name: "", enable_cwip_accounting: false });
      setShowCreateForm(false);
      mutate();
    } catch (error) {
      console.error("Failed to create category:", error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Asset Categories</h1>
          <p className="text-sm text-slate-muted mt-1">
            Configure depreciation settings for asset groups
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => mutate()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 bg-slate-elevated hover:bg-slate-border/50 rounded-lg text-sm text-slate-muted hover:text-foreground transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
          </button>
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 rounded-lg text-sm text-foreground transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Category
          </button>
        </div>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="font-semibold text-foreground mb-4">Create Asset Category</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-muted mb-1">Category Name *</label>
                <input
                  type="text"
                  value={newCategory.asset_category_name}
                  onChange={(e) => setNewCategory((prev) => ({ ...prev, asset_category_name: e.target.value }))}
                  placeholder="e.g., Office Equipment"
                  className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                  required
                />
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="cwip"
                  checked={newCategory.enable_cwip_accounting}
                  onChange={(e) => setNewCategory((prev) => ({ ...prev, enable_cwip_accounting: e.target.checked }))}
                  className="w-4 h-4 rounded border-slate-border bg-slate-elevated focus:ring-indigo-500"
                />
                <label htmlFor="cwip" className="text-sm text-slate-muted">
                  Enable CWIP Accounting (Capital Work in Progress)
                </label>
              </div>
            </div>
            <div className="flex items-center gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="px-4 py-2 text-sm text-slate-muted hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 rounded-lg text-sm text-foreground transition-colors"
              >
                Create Category
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Categories List */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-slate-muted">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
            Loading categories...
          </div>
        ) : categories.length === 0 ? (
          <div className="p-12 text-center text-slate-muted">
            <Layers className="w-8 h-8 mx-auto mb-3 opacity-50" />
            <p className="font-medium">No categories found</p>
            <p className="text-sm mt-1">Create your first asset category to get started</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-border">
            {categories.map((category) => {
              const isExpanded = expandedCategories.has(category.id);
              const hasFinanceBooks = category.finance_books && category.finance_books.length > 0;

              return (
                <div key={category.id}>
                  <div
                    className="flex items-center justify-between px-4 py-3 hover:bg-slate-elevated/30 transition-colors cursor-pointer"
                    onClick={() => hasFinanceBooks && toggleExpand(category.id)}
                  >
                    <div className="flex items-center gap-3">
                      {hasFinanceBooks ? (
                        <button className="p-1 text-slate-muted hover:text-foreground">
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </button>
                      ) : (
                        <div className="w-6" />
                      )}
                      <div className="p-2 rounded-lg bg-indigo-500/20">
                        <Layers className="w-4 h-4 text-indigo-300" />
                      </div>
                      <div>
                        <p className="font-medium text-foreground">{category.asset_category_name}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          {category.enable_cwip_accounting && (
                            <span className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-300 rounded-full">
                              CWIP Enabled
                            </span>
                          )}
                          {hasFinanceBooks && (
                            <span className="text-xs text-slate-muted">
                              {category.finance_books!.length} finance book{category.finance_books!.length !== 1 ? "s" : ""}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); }}
                        className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
                        title="Edit"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); }}
                        className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
                        title="Settings"
                      >
                        <Settings className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Finance Books (Expanded) */}
                  {isExpanded && hasFinanceBooks && (
                    <div className="bg-slate-elevated/20 border-t border-slate-border">
                      <div className="px-4 py-2">
                        <p className="text-xs text-slate-muted uppercase tracking-wider mb-2">Finance Books</p>
                        <div className="space-y-2">
                          {category.finance_books!.map((book, idx) => (
                            <div
                              key={idx}
                              className="bg-slate-card border border-slate-border rounded-lg p-3"
                            >
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                                <div>
                                  <p className="text-xs text-slate-muted">Finance Book</p>
                                  <p className="text-foreground">{book.finance_book || "Default"}</p>
                                </div>
                                <div>
                                  <p className="text-xs text-slate-muted">Method</p>
                                  <p className="text-foreground capitalize">{book.depreciation_method || "-"}</p>
                                </div>
                                <div>
                                  <p className="text-xs text-slate-muted">Depreciations</p>
                                  <p className="text-foreground">{book.total_number_of_depreciations}</p>
                                </div>
                                <div>
                                  <p className="text-xs text-slate-muted">Frequency</p>
                                  <p className="text-foreground">{book.frequency_of_depreciation} months</p>
                                </div>
                              </div>
                              {(book.fixed_asset_account || book.depreciation_expense_account) && (
                                <div className="grid grid-cols-2 gap-3 text-sm mt-3 pt-3 border-t border-slate-border">
                                  {book.fixed_asset_account && (
                                    <div>
                                      <p className="text-xs text-slate-muted">Fixed Asset Account</p>
                                      <p className="text-foreground text-xs">{book.fixed_asset_account}</p>
                                    </div>
                                  )}
                                  {book.depreciation_expense_account && (
                                    <div>
                                      <p className="text-xs text-slate-muted">Depreciation Expense</p>
                                      <p className="text-foreground text-xs">{book.depreciation_expense_account}</p>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
