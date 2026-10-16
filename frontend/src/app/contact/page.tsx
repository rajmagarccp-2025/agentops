"use client";

import React from "react";
import { ContactForm } from "../../components/contact-form";

export default function ContactPage() {
  return (
    <main className="contact-page">
      <div className="contact-page__header">
        <span className="contact-page__eyebrow">Support &amp; Engagement</span>
        <h1>Contact Platform Engineering &amp; Enterprise Support</h1>
      </div>
      <ContactForm />
    </main>
  );
}
