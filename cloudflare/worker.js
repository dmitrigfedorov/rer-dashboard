const REPOSITORY = "dmitrigfedorov/rer-dashboard";
const WORKFLOW_FILE = "refresh-schedule.yml";
const REF = "main";

async function dispatchWorkflow(env) {
  if (!env.GITHUB_TOKEN) {
    throw new Error("Missing GITHUB_TOKEN Worker secret.");
  }

  const url = `https://api.github.com/repos/${REPOSITORY}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "rer-dashboard-cloudflare-cron",
    },
    body: JSON.stringify({ ref: REF }),
  });

  if (response.status !== 204) {
    const detail = (await response.text()).slice(0, 500);
    throw new Error(`GitHub workflow dispatch failed (${response.status}): ${detail}`);
  }

  console.log(`Dispatched ${REPOSITORY}/.github/workflows/${WORKFLOW_FILE} at ${new Date().toISOString()}`);
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(dispatchWorkflow(env));
  },
};
