"use client";

import React, { useState } from "react";

export function ContactForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState("support");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string; ticketId?: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null);

    // Validation
    if (!name.trim() || !email.trim() || !subject.trim() || !message.trim()) {
      setFeedback({ type: "error", message: "Please fill in all required fields." });
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      setFeedback({ type: "error", message: "Please enter a valid email address." });
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await fetch("/api/proxy/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          subject: subject.trim(),
          message: message.trim(),
          category,
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        let errStr = "Unable to submit inquiry. Please try again.";
        if (typeof data.detail === "string") {
          errStr = data.detail;
        } else if (Array.isArray(data.detail)) {
          errStr = data.detail
            .map((d: { msg?: string }) => (typeof d === "string" ? d : d.msg || JSON.stringify(d)))
            .join("; ");
        } else if (typeof data.error === "string") {
          errStr = data.error;
        } else if (data.detail) {
          errStr = JSON.stringify(data.detail);
        }
        throw new Error(errStr);
      }

      setFeedback({
        type: "success",
        message: data.message || "Thank you! Your message has been submitted to AgentOps engineering support.",
        ticketId: data.ticket_id,
      });

      // Clear fields
      setName("");
      setEmail("");
      setSubject("");
      setMessage("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to send message. Please try again.";
      setFeedback({ type: "error", message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="contact-card">
      <div className="contact-card__heading">
        <h2>
          Contact AgentOps Engineering & Support
        </h2>
        <p>
          Connect directly with our platform engineers and enterprise support team.
        </p>
      </div>

      {feedback && (
        <div className={`contact-feedback contact-feedback--${feedback.type}`}>
          <div className="contact-feedback__message">
            <span>{feedback.type === "success" ? "✓" : "⚠️"}</span>
            <span>{feedback.message}</span>
          </div>
          {feedback.ticketId && (
            <div className="contact-feedback__ticket">
              Ticket Reference ID: <strong>{feedback.ticketId}</strong>
            </div>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="contact-form">
        <div className="contact-form__row contact-form__row--equal">
          <div className="contact-form__field">
            <label htmlFor="contact-name">
              Your Name *
            </label>
            <input
              type="text"
              id="contact-name"
              className="contact-form__control"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Alex Rivera"
              required
            />
          </div>

          <div className="contact-form__field">
            <label htmlFor="contact-email">
              Email Address *
            </label>
            <input
              type="email"
              id="contact-email"
              className="contact-form__control"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex.rivera@enterprise.com"
              required
            />
          </div>
        </div>

        <div className="contact-form__row contact-form__row--subject">
          <div className="contact-form__field">
            <label htmlFor="contact-subject">
              Subject *
            </label>
            <input
              type="text"
              id="contact-subject"
              className="contact-form__control"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Enterprise Keycloak SSO Onboarding Inquiry"
              required
            />
          </div>

          <div className="contact-form__field">
            <label htmlFor="contact-category">
              Category
            </label>
            <select
              id="contact-category"
              className="contact-form__control"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="support">Technical Support</option>
              <option value="enterprise">Enterprise Sales</option>
              <option value="security">Security & Compliance</option>
              <option value="feedback">Product Feedback</option>
            </select>
          </div>
        </div>

        <div className="contact-form__field">
          <label htmlFor="contact-message">
            Message *
          </label>
          <textarea
            id="contact-message"
            className="contact-form__control contact-form__message"
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Describe your inquiry, architecture requirements, or issue details..."
            required
          />
        </div>

        <button
          type="submit"
          id="contact-submit-btn"
          className="contact-form__submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Submitting Inquiry..." : "Send Message to AgentOps Team →"}
        </button>
      </form>
    </section>
  );
}
