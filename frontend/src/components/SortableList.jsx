import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
  rectSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";

/**
 * Generic sortable list. Children are rendered via `renderItem(item, dragHandle, index)`.
 * - `direction`: "vertical" | "grid" (uses appropriate sorting strategy)
 * - `dragHandle` is a small grip icon node — drag is restricted to it so form
 *   inputs and buttons inside the card work normally.
 */
export function SortableList({
  items,
  getId,
  onReorder,
  direction = "vertical",
  renderItem,
  testId,
  className = "",
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );
  const handleEnd = (e) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((x) => getId(x) === active.id);
    const newIndex = items.findIndex((x) => getId(x) === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const next = arrayMove(items, oldIndex, newIndex);
    onReorder(next.map((x) => getId(x)));
  };
  const strategy =
    direction === "grid" ? rectSortingStrategy : verticalListSortingStrategy;
  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleEnd}>
      <SortableContext items={items.map((x) => getId(x))} strategy={strategy}>
        <div data-testid={testId} className={className}>
          {items.map((item, i) => (
            <SortableRow
              key={getId(item)}
              id={getId(item)}
              direction={direction}
              renderItem={(handle) => renderItem(item, handle, i)}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}

function SortableRow({ id, direction, renderItem }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
    zIndex: isDragging ? 10 : "auto",
  };
  const handle = (
    <button
      type="button"
      data-testid={`drag-handle-${id}`}
      {...attributes}
      {...listeners}
      className="cursor-grab active:cursor-grabbing text-[#A1A1AA] hover:text-white p-1 rounded hover:bg-white/5"
      aria-label="Reorder"
      title="Drag to reorder"
    >
      <GripVertical className="w-4 h-4" />
    </button>
  );
  return (
    <div ref={setNodeRef} style={style} className={direction === "grid" ? "" : "mb-3"}>
      {renderItem(handle)}
    </div>
  );
}
