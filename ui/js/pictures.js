// The picture-password pictures. The ids must match the server's list
// (internal/auth); the labels are what students hear and see.

export const PICTURES = [
  { id: "apple", label: "Apple" },
  { id: "cat", label: "Cat" },
  { id: "fish", label: "Fish" },
  { id: "rocket", label: "Rocket" },
  { id: "star", label: "Star" },
  { id: "sun", label: "Sun" },
  { id: "tree", label: "Tree" },
  { id: "car", label: "Car" },
  { id: "umbrella", label: "Umbrella" },
];

export const PICTURE_COUNT = 3;

export function pictureLabel(id) {
  return PICTURES.find((p) => p.id === id)?.label ?? id;
}
