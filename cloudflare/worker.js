const WORKFLOW_FILE = "refresh-schedule.yml";

async function dispatchWorkflow(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: env.GITHUB_REF || "main" }),
  });

  if (response.status !== 204) {
    const detail = (await response.text()).slice(0, 500);
    throw new Error(`GitHub workflow dispatch failed (${response.status}): ${detail}`);
  }

  console.log(`Dispatched ${env.GITHUB_OWNER}/${env.GITHUB_REPO}/${WORKFLOW_FILE} at ${new Date().toISOString()}`);
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(dispatchWorkflow(env));
  },
};
