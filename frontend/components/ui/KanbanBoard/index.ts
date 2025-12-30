// =============================================================================
// KANBAN BOARD - Barrel Export
// =============================================================================

export { KanbanBoard, type KanbanBoardProps } from './KanbanBoard';
export { KanbanColumn, type KanbanColumnProps } from './KanbanColumn';
export {
  KanbanCard,
  OpportunityCard,
  TaskCard,
  type KanbanCardProps,
  type OpportunityCardProps,
  type OpportunityCardData,
  type TaskCardProps,
  type TaskCardData,
} from './KanbanCard';
export {
  type KanbanItem,
  type KanbanColumn as KanbanColumnType,
  type DragResult,
  KANBAN_COLORS,
  getColumnColors,
} from './types';

// Default export
export { KanbanBoard as default } from './KanbanBoard';
