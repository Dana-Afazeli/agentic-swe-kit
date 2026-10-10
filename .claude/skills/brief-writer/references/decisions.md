# A decision put to the maintainer: one wrong, one right

The maintainer decides too many things to remember any of them, and reads your question with no
memory of the conversation around it. So each decision is asked alone, and carries everything
needed to answer it: the situation in plain words, the options and what each costs to build and
to whoever uses the result, your recommendation, and the one word to reply.

The example is invented: a service that sends reminders.

## Wrong

> Three things are still open from above: (1) the retries: cap or no cap? (2) the queue file,
> same question; (3) do we log the body? I'd go with the first option on all three unless you
> object.

What is wrong with it:
- Three decisions in one question. One answer cannot be given, and "ok" approves all three.
- "From above", "the first option", "the queue file": labels of the conversation. A day later
  nobody, the maintainer included, can say what was decided.
- No cost for any option, to build or to the user, so there is nothing to weigh.
- "Unless you object" turns silence into a decision.

## Right

One of the three, asked on its own:

> **How often is a reminder sent again when delivery fails?**
>
> The situation: when the delivery service answers with an error, the reminder is sent again
> every 30 seconds, for ever. On the day the delivery service was down for two hours, one
> reminder was sent 240 times once it came back (counted in the log of that day:
> `grep -c "retry id=4711" service.log` prints 240).
>
> - **cap**: at most five tries, then the reminder is marked failed. To build: about 10 lines.
>   What a user notices: after two and a half minutes of outage the reminder never arrives; it
>   shows as failed in their list, and they have to send it again by hand.
> - **back off**: the wait doubles after each try, up to an hour, with no cap. To build: about
>   20 lines. What a user notices: nothing is lost, and after a long outage a reminder can
>   arrive up to an hour after the delivery service is back.
> - **keep**: every 30 seconds, for ever. To build: nothing. What a user notices: at the next
>   outage, the same reminder 240 times in a row.
>
> I recommend **back off**: nothing is lost, and the flood cannot happen. Reply `cap`,
> `back off` or `keep`.

What makes it right:
- It can be read alone, a week later, by someone who was not there.
- Each option has both sides of its cost: what it takes to build, and how it shows itself to
  the person using the result (what they see, wait for, or have to do). "keep" is free to build
  and its whole cost is on the user's side; a list of build costs alone would have hidden that.
- The fact it rests on names the command that checked it.
- The recommendation comes with its reason, and the reply is one word.

## Recording the answer

Write down what the maintainer said, in their words, and what you made of it as a second thing:

> The maintainer: "back off, but stop after a day". Recorded as **back off**. My addition, not
> theirs: "a day" as 24 hours from the first failed try.

A choice you made yourself to carry out an answer is yours, and is recorded as yours. A later
reader takes "decided by the maintainer" at its word.
