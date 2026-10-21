// GUI smoke test: login → setup → picker → Free Play (autosave) → Save my
// work / Open my work → log out and back in. Screenshots go to
// test-results/screenshots at 1366×768 and 1920×1080.
import { test, expect } from "@playwright/test";

const SIZES = [
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
];

async function shoot(page, name) {
  for (const size of SIZES) {
    await page.setViewportSize(size);
    await page.waitForTimeout(250); // let dialogs finish fading in
    await page.screenshot({ path: `test-results/screenshots/${name}-${size.width}x${size.height}.png` });
  }
  await page.setViewportSize(SIZES[0]);
}

async function tapPictures(page, names) {
  for (const n of names) await page.locator(`.picture[aria-label='${n}']`).click();
}

async function makeProfile(page, { cls, names, school, pictures, screenshots = false }) {
  await page.goto("/");
  await page.getByRole("button", { name: cls }).click();
  await page.locator(".new-tile").click();
  await page.getByLabel("First name", { exact: true }).fill(names[0]);
  for (let i = 1; i < names.length; i++) {
    await page.getByRole("button", { name: /Add another name/ }).click();
    await page.getByLabel(`First name ${i + 1}`).fill(names[i]);
  }
  await page.getByLabel("Your school").fill(school);
  if (screenshots) await shoot(page, "03-new-profile");
  await page.getByRole("button", { name: "Next" }).click();
  await tapPictures(page, pictures);
  if (screenshots) await shoot(page, "04-pick-pictures");
  await page.getByRole("button", { name: "Next" }).click();
  await tapPictures(page, pictures);
  await expect(page.getByText("Let's get you set up")).toBeVisible();
}

test("a student's whole first lesson", async ({ page }) => {
  const problems = [];
  page.on("pageerror", (e) => problems.push(e.message));

  // Welcome → class → names
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Welcome!" })).toBeVisible();
  const classes = await page.locator(".class-tile .tile-name").allTextContents();
  expect(classes).toEqual(["7B Monday", "9D Tuesday", "10A Thursday"]);
  await shoot(page, "01-welcome");
  await page.getByRole("button", { name: "9D Tuesday" }).click();
  await expect(page.getByText("No one has made a profile here yet")).toBeVisible();
  await shoot(page, "02-names-empty");

  // New profile, sharing a kit
  await makeProfile(page, { cls: "9D Tuesday", names: ["mia", "Leo"], school: "Eltham High School", pictures: ["Cat", "Rocket", "Apple"], screenshots: true });

  // Setup: help level and board
  await expect(page.getByText("Nice to meet you, Mia and Leo!")).toBeVisible();
  await page.getByText("Advanced", { exact: true }).click();
  await page.getByText("NodeMCU 1.0 (ESP8266)").click();
  await shoot(page, "05-setup");
  await page.getByRole("button", { name: "Let's go!" }).click();

  // The picker: Free Play first, projects with board notes
  await expect(page.getByRole("heading", { name: /Hi Mia and Leo!/ })).toBeVisible();
  const cards = page.locator(".project-grid > .card");
  await expect(cards.first()).toHaveClass(/freeplay-card/);
  await expect(page.locator(".project-card", { hasText: "Phone-controlled LED" })).toContainText("Works with your NodeMCU");
  await expect(page.locator(".project-card", { hasText: "Keypad Safe" })).toContainText("Needs a Uno or Mega");
  await expect(page.locator(".statusbar")).toContainText("Help: Advanced");
  await shoot(page, "06-picker");
  await page.locator(".nav-item", { hasText: "WiFi & IoT" }).click();
  await expect(page.locator(".project-card")).toHaveCount(6);
  await page.locator(".nav-item", { hasText: "All projects" }).click();

  // Free Play: type, and it saves by itself
  await page.locator(".freeplay-card").click();
  const editor = page.locator(".editor-text");
  await expect(editor).toBeVisible();
  await editor.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\n// My robot");
  await expect(page.locator(".save-status")).toHaveText("Saved ✓", { timeout: 5000 });
  await shoot(page, "07-free-play");
  await page.reload();
  await expect(page.locator(".editor-text")).toHaveValue(/\/\/ My robot/);

  // Settings
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("dialog", { name: "Settings" })).toBeVisible();
  await shoot(page, "08-settings");
  await page.getByRole("tab", { name: "My work" }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save my work" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^Mia-Leo_CircuitPath_\d{4}-\d{2}-\d{2}\.circuit$/);
  const saved = await download.path();
  await page.keyboard.press("Escape");

  // Log out, then a classmate opens Mia and Leo's file
  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await makeProfile(page, { cls: "9D Tuesday", names: ["Ava"], school: "Eltham High School", pictures: ["Star", "Sun", "Tree"] });
  await page.getByRole("button", { name: "Let's go!" }).click();
  await page.getByRole("button", { name: "Open my work" }).click();
  await page.locator("input[type=file]").setInputFiles(saved);
  await expect(page.getByText("This file belongs to Mia and Leo.")).toBeVisible();
  await page.getByRole("button", { name: "Open it" }).click();
  await expect(page.getByText("Your work is open.")).toBeVisible();
  await page.keyboard.press("Escape"); // closes just the message box
  await expect(page.getByRole("dialog", { name: "Settings" })).toBeVisible();
  await page.getByRole("dialog", { name: "Settings" }).getByRole("button", { name: "Cancel" }).click();
  await page.locator(".freeplay-card").click();
  await expect(page.locator(".editor-text")).toHaveValue(/\/\/ My robot/);
  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: "Log out" }).click();

  // Log back in: wrong pictures, then the right ones
  await page.getByRole("button", { name: "9D Tuesday" }).click();
  await page.locator(".user-tile", { hasText: "Mia and Leo" }).click();
  await tapPictures(page, ["Rocket", "Cat", "Apple"]);
  await expect(page.getByText("Those pictures don't match. Try again.")).toBeVisible();
  await shoot(page, "09-wrong-pictures");
  await tapPictures(page, ["Cat", "Rocket", "Apple"]);
  await expect(page.getByRole("heading", { name: /Hi Mia and Leo!/ })).toBeVisible();
  await expect(page.locator(".freeplay-card")).toContainText("Keep going");

  expect(problems).toEqual([]);
});
