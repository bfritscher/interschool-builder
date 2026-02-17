# Inter-School Software Development Auto Builder

This project provides an automated setup that simplifies the deployment process of your software projects.
Below, you will find detailed instructions on how the builder operates and sets up your project for testing environments [https://builder.rxq.ch/](https://builder.rxq.ch/).


## Features
- **Subdomain Hosting**: Individual projects are hosted as unique subdomains `[NM-groupname].rxq.ch`.
- **Base URL Rewriting**: Automatically updates the `baseURL` in `src/services/api.js` from localhost to `/api`.
- **Frontend Build**: Constructs the frontend using **Node.js 24**. Ensure your `package.json` file contains all necessary dependencies.
- **Django Setup**: Installs Django along with all required packages listed in `requirements.txt`.
- **Database Migrations**: Applies database migrations to keep your schema up-to-date.
- **Fixture Loading**: Loads JSON fixtures located in any `/backend/*/*fixture*/` directory, facilitating initial data setup. See [Django Fixtures Doc](https://docs.djangoproject.com/en/5.0/topics/db/fixtures/).
- **Development Server**: Runs Django using **Python 3.14** on the development server, allowing error messages to be visible on the test site.
- **Superadmin Creation**: A default superadmin account is created (`username: autoadmin`, `password: heg`) for initial access, but your users should be populated with fixtures.
- **Email Interception**: Configures a special email server to capture all outgoing emails, which can be accessed and reviewed at [https://mail.rxq.ch/](https://mail.rxq.ch/).
- **Build Info**: Commit of the files used is available at `/static/build.html` in django

## Additional Information

If you have specific requirements or need adjustments to the build process that are not covered by the default configuration, feel free to reach out for customization options to Boris Fritscher.
