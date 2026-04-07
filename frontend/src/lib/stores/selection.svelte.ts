let ids = $state(new Set<string>());

export const selection = {
	get ids() { return ids; },
	get count() { return ids.size; },

	add(id: string) { ids = new Set([...ids, id]); },
	remove(id: string) { ids = new Set([...ids].filter(x => x !== id)); },
	toggle(id: string) { ids.has(id) ? selection.remove(id) : selection.add(id); },
	addAll(newIds: string[]) { ids = new Set([...ids, ...newIds]); },
	clear() { ids = new Set(); },
	has(id: string) { return ids.has(id); },
	toArray() { return [...ids]; }
};
