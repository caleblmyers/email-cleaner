import { toast as sonner } from 'svelte-sonner';

export const toast = {
	show(msg: string, error = false) {
		if (error) sonner.error(msg);
		else sonner.success(msg);
	},
	error(msg: string) { sonner.error(msg); },
	info(msg: string) { sonner.info(msg); }
};
