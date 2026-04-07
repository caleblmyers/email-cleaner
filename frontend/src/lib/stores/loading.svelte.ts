let active = $state(false);
let message = $state('Loading...');

export const loading = {
	get active() { return active; },
	get message() { return message; },

	show(msg = 'Loading...') { message = msg; active = true; },
	hide() { active = false; }
};
