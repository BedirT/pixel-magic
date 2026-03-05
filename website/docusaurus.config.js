// @ts-check

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "Pixel Magic",
  tagline: "Workflow-native MCP toolkit for game-ready pixel art generation",
  url: "https://bedirt.github.io",
  baseUrl: "/pixel-magic/",
  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "throw",
  organizationName: "pixel-magic",
  projectName: "pixel-magic",
  i18n: {
    defaultLocale: "en",
    locales: ["en"]
  },
  presets: [
    [
      "classic",
      {
        docs: {
          path: "../docs",
          routeBasePath: "/",
          sidebarPath: require.resolve("./sidebars.js"),
          exclude: ["**/BENCHMARK_REPORT_2026-03-04.md"]
        },
        blog: false,
        theme: {
          customCss: require.resolve("./src/css/custom.css")
        }
      }
    ]
  ],
  themeConfig: {
    navbar: {
      title: "Pixel Magic",
      items: [
        {
          type: "docSidebar",
          sidebarId: "docsSidebar",
          position: "left",
          label: "Docs"
        },
        {
          href: "https://github.com/BedirT/pixel-magic",
          label: "GitHub",
          position: "right"
        }
      ]
    }
  }
};

module.exports = config;
