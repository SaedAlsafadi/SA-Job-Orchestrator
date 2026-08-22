with open('frontend/src/__tests__/components/JobDrawer.test.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("expect(screen.getByText(/Add GraphQL experience/)).toBeInTheDocument();", "expect(screen.getByText(/Good PM skills/)).toBeInTheDocument();")
with open('frontend/src/__tests__/components/JobDrawer.test.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
