import { z } from "zod";

// Shared form schema for "delete by period" dialogs (backup logs and reports).
// Both fields are YYYY-MM-DD strings; the range must be non-empty and ordered.
export const bulkPeriodSchema = z
  .object({
    date_from: z.string().min(1, "Start date is required"),
    date_to: z.string().min(1, "End date is required"),
  })
  .refine((data) => new Date(data.date_to) >= new Date(data.date_from), {
    message: "Start date must be on or before end date",
    path: ["date_from"],
  });

export type BulkPeriodValues = z.infer<typeof bulkPeriodSchema>;
