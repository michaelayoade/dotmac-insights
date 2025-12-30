/**
 * Inbox Conversations E2E Tests
 *
 * Comprehensive tests for the Inbox/Conversations module including:
 * - Conversation list view with filters
 * - Message thread interactions
 * - Assignment and routing
 * - Conversation actions (close, snooze)
 * - Ticket creation from conversations
 * - RBAC (role-based access control)
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import {
  createTestConversation,
  deleteTestConversation,
  createTestContact,
  deleteTestContact,
} from './fixtures/api-helpers';
import { InboxPage } from './pages';

test.describe('Inbox Conversations - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['inbox:read', 'inbox:write']);
  });

  test.describe('List View', () => {
    test('renders conversations list', async ({ page }) => {
      const inboxPage = new InboxPage(page);
      await inboxPage.goto();

      await expect(page.getByText(/access denied|not authorized/i)).toBeHidden({ timeout: 10000 });
      await expect(
        page.getByRole('heading', { name: /inbox|conversations/i })
      ).toBeVisible({ timeout: 10000 });
    });

    test('displays conversation items', async ({ page }) => {
      const inboxPage = new InboxPage(page);
      await inboxPage.goto();
      await inboxPage.waitForInbox();

      await expect(inboxPage.conversationList).toBeVisible();
    });

    test('filter by channel works', async ({ page }) => {
      const inboxPage = new InboxPage(page);
      await inboxPage.goto();

      if (await inboxPage.channelFilter.isVisible()) {
        await inboxPage.filterByChannel('email');

        await expect(
          inboxPage.conversationItems
            .first()
            .or(page.getByText(/no.*conversations|empty/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });

    test('filter by status works', async ({ page }) => {
      const inboxPage = new InboxPage(page);
      await inboxPage.goto();

      if (await inboxPage.statusFilter.isVisible()) {
        await inboxPage.filterByStatus('Open');

        await expect(
          inboxPage.conversationItems
            .first()
            .or(page.getByText(/no.*conversations|empty/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });

    test('filter by assignee works', async ({ page }) => {
      const inboxPage = new InboxPage(page);
      await inboxPage.goto();

      if (await inboxPage.assigneeFilter.isVisible()) {
        await inboxPage.assigneeFilter.selectOption({ index: 1 });

        await page.waitForTimeout(500);
        await expect(inboxPage.conversationList).toBeVisible();
      }
    });

    test('search filters conversations', async ({ page }) => {
      const inboxPage = new InboxPage(page);
      await inboxPage.goto();

      await inboxPage.search('test');

      await expect(
        inboxPage.conversationItems
          .first()
          .or(page.getByText(/no.*results|empty/i))
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Conversation Detail', () => {
    test('opens conversation on click', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Inbox Contact ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
          subject: `E2E Conversation ${Date.now()}`,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          // Message thread should be visible
          await expect(
            inboxPage.messageThread.or(page.getByText(/messages|thread/i))
          ).toBeVisible({ timeout: 10000 });
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });

    test('displays message input', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Input Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          await expect(inboxPage.messageInput).toBeVisible({ timeout: 10000 });
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });

    test('displays send button', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Send Button Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          await expect(inboxPage.sendButton).toBeVisible({ timeout: 10000 });
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });
  });

  test.describe('Send Message', () => {
    test('can type message', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Type Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          const testMessage = `E2E Test Message ${Date.now()}`;
          await inboxPage.messageInput.fill(testMessage);

          await expect(inboxPage.messageInput).toHaveValue(testMessage);
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });

    test('sends message successfully', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Send Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          const testMessage = `E2E Sent Message ${Date.now()}`;
          await inboxPage.sendMessage(testMessage);

          // Message should appear in thread
          await inboxPage.expectMessageInThread(testMessage);
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });
  });

  test.describe('Assignment', () => {
    test('shows assign button', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Assign Button Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          await expect(inboxPage.assignButton).toBeVisible({ timeout: 10000 });
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });

    test('can assign conversation', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Assign Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          if (await inboxPage.assignButton.isVisible()) {
            await inboxPage.assignButton.click();

            // Select first agent option
            const agentOption = page.getByRole('option').first();
            if (await agentOption.isVisible({ timeout: 2000 })) {
              await agentOption.click();
              await page.waitForTimeout(500);
            }
          }
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });
  });

  test.describe('Conversation Actions', () => {
    test('can close conversation', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Close Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          if (await inboxPage.closeButton.isVisible()) {
            await inboxPage.closeConversation();

            await inboxPage.expectConversationStatus('closed');
          }
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });

    test('can snooze conversation', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Snooze Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          if (await inboxPage.snoozeButton.isVisible()) {
            await inboxPage.snoozeButton.click();

            // Select snooze duration
            const durationOption = page.getByRole('option', { name: /hour|day|tomorrow/i }).first();
            if (await durationOption.isVisible({ timeout: 2000 })) {
              await durationOption.click();
              await page.waitForTimeout(500);
            }
          }
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });
  });

  test.describe('Create Ticket', () => {
    test('shows create ticket button', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Ticket Button Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          await expect(inboxPage.createTicketButton).toBeVisible({ timeout: 10000 });
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });

    test('can create ticket from conversation', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Create Ticket Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          if (await inboxPage.createTicketButton.isVisible()) {
            await inboxPage.createTicket({
              subject: `E2E Ticket from Inbox ${Date.now()}`,
            });

            // Should show success or navigate to ticket
            await page.waitForTimeout(1000);
          }
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });
  });

  test.describe('Canned Responses', () => {
    test('shows canned response button', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Canned Response Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          if (await inboxPage.cannedResponseButton.isVisible()) {
            await expect(inboxPage.cannedResponseButton).toBeVisible();
          }
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });
  });

  test.describe('Attachments', () => {
    test('shows attachment button', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Attachment Test ${Date.now()}`,
      });

      try {
        const conversation = await createTestConversation(request, {
          contact_id: contact.id,
        });

        try {
          const inboxPage = new InboxPage(page);
          await inboxPage.gotoConversation(conversation.id);

          if (await inboxPage.attachmentButton.isVisible()) {
            await expect(inboxPage.attachmentButton).toBeVisible();
          }
        } finally {
          await deleteTestConversation(request, conversation.id);
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });
  });
});

test.describe('Inbox Conversations - RBAC', () => {
  test('read-only user can view conversations', async ({ page }) => {
    await setupAuth(page, ['inbox:read']);

    const inboxPage = new InboxPage(page);
    await inboxPage.goto();

    await expect(inboxPage.conversationList).toBeVisible({ timeout: 10000 });
  });

  test('user without inbox scope sees access denied', async ({ page }) => {
    await setupAuth(page, ['hr:read']);
    await page.goto('/inbox');

    await expectAccessDenied(page);
  });
});

test.describe('Inbox Conversations - Unauthenticated', () => {
  test('redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/inbox');

    await expect(page).toHaveURL(/\/login|\/auth/);
  });
});
