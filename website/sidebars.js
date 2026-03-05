/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docsSidebar: [
    "intro",
    {
      type: "category",
      label: "Getting Started",
      items: ["getting-started/installation", "getting-started/quickstart"]
    },
    {
      type: "category",
      label: "MCP",
      items: ["mcp/setup", "mcp/tool-reference"]
    },
    {
      type: "category",
      label: "Architecture",
      items: ["architecture/runtime"]
    },
    {
      type: "category",
      label: "Configuration",
      items: ["configuration/providers-and-env"]
    },
    {
      type: "category",
      label: "Evaluation & Testing",
      items: ["evaluation/testing-and-judge"]
    },
    {
      type: "category",
      label: "Migration",
      items: ["migration/mainline-cleanup"]
    },
    {
      type: "category",
      label: "Troubleshooting",
      items: ["troubleshooting/common-issues"]
    }
  ]
};

module.exports = sidebars;
