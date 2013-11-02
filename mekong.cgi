#!/usr/bin/perl -w
# written by andrewt@cse.unsw.edu.au October 2013
# as a starting point for COMP2041 assignment 2
# http://www.cse.unsw.edu.au/~cs2041/assignments/mekong/

use warnings;
use strict;
use CGI qw/:all/;
use CGI::Cookie;
use HTML::Template;
use Switch;
use autodie;

######################################
###########global variables###########
######################################
our $base_dir = ".";
our $books_file = "$base_dir/books.json";
our $orders_dir = "$base_dir/orders";
our $baskets_dir = "$base_dir/baskets";
our $users_dir = "$base_dir/users";
our $last_error = "";
our %user_details = ();
our %book_details = ();
our $book_read = 0;
our %attribute_names = ();
our $loggedIn = 0;
our $id;
our @new_account_rows = (
          'login|Login:|10',
          'password|Password:|10',
          'name|Full Name:|50',
          'street|Street:|50',
          'city|City/Suburb:|25',
          'state|State:|25',
          'postcode|Postcode:|25',
          'email|Email Address:|35'
          );
our $debug = 0;
$| = 1;
######################################

if (!@ARGV) {
    # run as a CGI script
    cgi_main();    
} else {
    # for debugging purposes run from the command line
    console_main();
}
exit 0;

# This is very simple CGI code that goes straight
# to the search screen and it doesn't format the
# search results at all
sub cgi_main {
    print "Content-Type: text/html\n\n";
    
    set_global_variables();

    my $page;
    my %template_variables = ();
    my $action = param('action');
    my %cookies = CGI::Cookie->fetch();
    
    if (legalCookie($cookies{ID})) {
        $loggedIn = 1;
        my @arr = split(/:/, $cookies{ID}->value);
        $id = shift(@arr);
    }

    if (not defined $action) {
        if ($loggedIn) {
            $action = "home";
        } else {
            $action = "";
        }
    } 
    
    switch($action) {
        case "login"         {$page = check_user(\%template_variables)}
        case "signup"        {$page = signup_form(\%template_variables, 0)}
        case "registered"    {$page = register(\%template_variables)}
        case "search"        {$page = search_results(\%template_variables)}
        case "home"          {$page = search_form(\%template_variables, 0)}
        case "log"           {$page = login_out(\%template_variables)}
        case "basket"        {$page = basket_page(\%template_variables)}
        case /^details /     {$page = details_page(\%template_variables, $action)}
        case /^add_([^ ]*) / {$page = add_book(\%template_variables, $action)}
        case /^drop /        {$page = drop_book(\%template_variables, $action)}
        case "forgot"        {$page = forgot_password(\%template_variables)}
        case "recover"       {$page = recover_password(\%template_variables, 0)}             
        else                 {$page = noAction(\%template_variables)}
    }

    print "\n";
    print page_header($action);
    my $template = HTML::Template->new(filename => "$page.template");    
    $template->param(%template_variables);
    print $template->output;
    print $loggedIn;
    print page_trailer();
}

sub recover_password{
    my ($template_variables) = @_;
    my $username = param('username');

    if (not legal_login($username) or not -e "$users_dir/$username") {
        $last_error = "Invalid username.";
        return forgot_password($template_variables, 1);
    }    

    #TODO email logic
    return login_form($template_variables, 0);
}

sub forgot_password {
    (my $template_variables, my $error) = @_;

    if ($error) {
        $$template_variables{ERROR} = $last_error;    
    }

    return "forgot_password";
}

sub change_password {

}

sub noAction {
    (my $template_variables) = @_;
    my $username; 
    my $confNum;
   
    if (not defined $ENV{QUERY_STRING}) {
        return login_form($template_variables, 0);
    }

    if ($ENV{QUERY_STRING} =~ /^id=(.*)&conf=([0-9]*)$/) {
        $username = $1;
        $confNum = $2;
        if (legal_login($username) and -e "$users_dir/$username") {
            if (not confirmed($username)) {
                if (confirm_email($username, $confNum)) {
                    $last_error = "email confirmed!";
                    return login_form($template_variables, 1);   
                }
            }
        }
        $last_error = "invalid url";
        return login_form($template_variables, 1);
    } elsif (0) {

    } else {
        return login_form($template_variables, 0);
    }
}

sub add_book {
    (my $template_variables, my $action) = @_;

    $action =~ /^add_([^ ]*) (.*)/;
    my $prevPage = $1;
    my $isbn = $2;

    if (not $loggedIn) {
        $last_error = "Must be logged in to add books.";
        return login_form($template_variables, 1); 
    } elsif (not defined $prevPage or not legal_isbn($isbn)) {
        $last_error = "Invalid add request.";
        return search_form($template_variables, 1);
    }

    if (not -d $baskets_dir) {
        mkdir($baskets_dir);
    }
    
    if ($prevPage eq "search") {
        add_basket($id, $isbn);
        return search_results($template_variables);    
    } elsif ($prevPage eq "details") {
        add_basket($id, $isbn);
        return details_page($template_variables, "details " . $isbn);
    } else {
        $last_error = "Invalid add request.";
        return search_form($template_variables, 1);
    }
}

sub drop_book {
    (my $template_variables, my $action) = @_;
    $action =~ /^drop (.*)/;
    my $isbn = $1;

    if (not $loggedIn) {
        $last_error = "Must be logged in to remove books.";
        return login_form($template_variables, 1); 
    } elsif (not legal_isbn($isbn)) {
        $last_error = "Invalid remove request.";
        return search_form($template_variables, 1);
    }

    if (not $book_read) {
        read_books($books_file);
    }

    delete_basket($id, $isbn);
    return basket_page($template_variables);    
}

sub details_page {
    (my $template_variables, my $action) = @_;

    $action =~ /details (.*)/;
    my $isbn = $1;
 
    if (not legal_isbn($isbn)) {
        $last_error = "Isbn is not valid.";
        return search_form($template_variables, 1);
    }

    if (not $book_read) {
        read_books($books_file);
    }

    $$template_variables{isbn} = $isbn;

    my @fields = ("title", "productdescription", "mediumimageurl", "authors",
               "binding", "catalog", "ean", "price", "publication_date",
               "publisher", "releasedate", "salesrank", "year");

    foreach my $field (@fields) {
        if (defined $book_details{$isbn}{$field}) {
            $$template_variables{$field} = $book_details{$isbn}{$field};
        } else {
            $$template_variables{$field} = "";
        }
    }

    return "details_page";
}

sub login_out {
    (my $template_variables) = @_;

    if ($loggedIn) {
        my $cookie = CGI::Cookie->new(-name=>'ID', -value=>"");
        $cookie->bake();
    }

    $loggedIn = 0;
    return "login_form";
}

sub legalCookie {
    (my $cookie) = @_;
    my @arr;

    if (not defined $cookie or not defined $cookie->value or $cookie->value eq "") {
        return 0;
    }

    @arr = split(/:/, $cookie->value);
    if (not legal_login($arr[0])) {
        return 0;
    } elsif (not legal_password($arr[1])) {
        return 0;
    } elsif (not authenticate($arr[0], $arr[1])) {
        return 0;
    } else {
        return 1;
    }
}

sub basket_page {
    (my $template_variables) = @_;
    my @isbns;
    my @rows;
    
    if (not $loggedIn) {
        $last_error = "Must be logged in to check basket.";
        return login_form($template_variables, 1);
    }
    
    if (not $book_read) {
        read_books($books_file);
    }

    @isbns = read_basket($id);
 
    foreach my $isbn (@isbns) {
        my $newRow = makeRow($isbn);
        $newRow .= <<eof;
        <td><button class="btn" type="submit" name="action" value="drop $isbn">Drop</button><br>
        <button class="btn" type="submit" name="action" value="details $isbn">Details</button><br></td>
    </tr>
eof
        push(@rows, $newRow);        
    }

    $$template_variables{TABLE_ROWS} = "@rows";    
    $$template_variables{TOTAL_PRICE} = total_books(@isbns);
    
    return "basket_page";
}

sub login_form {
    (my $template_variables, my $error) = @_;

    if ($loggedIn) {
        $last_error = "Already logged in.";
        return search_form($template_variables, 1);
    }

    if ($error) {
        $$template_variables{ERROR} = $last_error;
    }

    return "login_form";
}

sub register {
    (my $template_variables) = @_;

    if ($loggedIn) {
        $last_error = "Already logged in.";
        return search_form($template_variables, 1);
    }

    my $username = param('username');
    my $password = param('password');
    my $notComplete = 0;

    my @userDetails = (param('fullname'), param('street'), param('city'), 
                       param('state'), param('postcode'), param('email'));

    if (not legal_login($username)) {
        return signup_form($template_variables, 1);
    } elsif (not legal_password($password)) {
        return signup_form($template_variables, 1);
    } else {
        foreach my $detail (@userDetails) {
            if ($detail eq "") {
                $notComplete = 1;
            }
        }
         
        if ($notComplete) {
            $last_error = "Registration form is incomplete.";
            return signup_form($template_variables, 1);
        } elsif (-e "$users_dir/$username") {
            $last_error = "Username already exists.";
            return signup_form($template_variables, 1);
        } else {
            addUser($username, $password, @userDetails);            
            return search_form($template_variables, 0);
        }
    }
}

sub addUser {
    my @userDetails = @_;
    my $i = 0;
    
    if (not -d $users_dir) {
        mkdir($users_dir);
    }

    my $email;
    open(USER, ">", "$users_dir/$userDetails[0]");
    
    foreach my $field (qw(login password name street city state postcode email)) {
        if ($field eq "email") {
            $email = $userDetails[$i];
        } 
        print(USER "$field=$userDetails[$i]\n");
        $i++;
    }
    
    my $randVar = int(rand(10000000));
    print(USER "conf=" . $randVar . "\n");
    
    `echo "$ENV{REDIRECT_SCRIPT_URI}?name=$userDetails[0]&id=$randVar" 
    | mutt -s 'Mekong Registration' -- "$email"`;
    
    close(USER);
}

sub signup_form {
    (my $template_variables, my $error) = @_;
    
    if ($error) {
        $$template_variables{ERROR} = $last_error;
    }

    return "signup_form";
}


sub confirm_email {
    (my $username, my $confirmNum) = @_;
    my $str = "";
    my $retVal = 1;

    open(USER, "<", "$users_dir/$username");
    
    while (my $line = <USER>) {
        if ($line =~ /^conf=(.*)\n/) {
            if ($1 == $confirmNum) {
                $retVal = 1;
            } else {
                $retVal = 0;
                $str .=  $line;
            }
        } else {
            $str .= $line;
        }
    }

    close(USER);
    open(USER, ">", "$users_dir/$username");
    
    print(USER $str);

    return $retVal;
}

sub confirmed {
    (my $username) = @_;
    my $retVal = 1;

    open(USER, "<", "$users_dir/$username");
    
    while (my $line = <USER>) {
        if ($line =~ /^conf=(.*)\n/) {
            $retVal = 0;
        }
    }

    close(USER);
    return $retVal;
}

#check if a given username/password exist and returns appropriate page
sub check_user {
    (my $template_variables) = @_;

    if ($loggedIn) {
        $last_error = "Already logged in.";
        return search_form($template_variables, 1);
    }

    my $username = param('username');
    my $password = param('password');

    if (not legal_login($username)) {
        return login_form($template_variables, 1);
    } elsif (not legal_password($password)) {
        return login_form($template_variables, 1);
    } elsif (not authenticate($username, $password)) {
        return login_form($template_variables, 1);
    } elsif (not confirmed($username, -1)) {
        $last_error = "Please confirm your email.";
        return login_form($template_variables, 1);
    } else {
        my $cookie = CGI::Cookie->new(-name=>'ID', -value=>"$username:$password");
        $cookie->bake();
        $loggedIn = 1;
        return search_form($template_variables, 0);
    }
}

# simple search form
sub search_form {
    (my $template_variables, my $error) = @_;
    if ($error) {
        $$template_variables{ERROR} = $last_error;
    }

    return "search_form";
}

#display of search results
sub search_results {
    (my $template_variables) = @_;

    if (not $book_read) {
        read_books($books_file);
    }

    my $search_terms = param('searchres');
    my @matching_isbns = search_books($search_terms);
    my @table_rows;
    my $newRow;    

    $$template_variables{SEARCH_TERMS} = $search_terms;
    foreach my $isbn (@matching_isbns) {
        $newRow = makeRow($isbn);
        $newRow .= <<eof;
        <td><button class="btn" type="submit" name="action" value="add_search $isbn">Add</button><br>
        <button class="btn" type="submit" name="action" value="details $isbn">Details</button><br></td>
    </tr>
eof
        push(@table_rows, $newRow);
    }

    $$template_variables{TABLE_ROWS} = "@table_rows";
    return "search_results";
}

sub makeRow {
    (my $isbn) = @_;
    if (not defined $book_details{$isbn}{smallimageurl}) {
        $book_details{$isbn}{smallimageurl} = "";
    } 

    if (not defined $book_details{$isbn}{authors}) {
        $book_details{$isbn}{authors} = "";
    }

    return <<eof;
    <tr>
        <td><img src="$book_details{$isbn}{smallimageurl}" /></td>
        <td><p>$book_details{$isbn}{title}</p>
            <p>$book_details{$isbn}{authors}</p></td>
        <td>$book_details{$isbn}{price}</td>
eof
}

#
# HTML at top of every screen
#
sub page_header() {
    (my $action) = @_;
    my %template_variables;

    if($loggedIn) {
        $template_variables{LOG} = "Logout";
    } else {
        $template_variables{LOG} = "Login";
    }
    my $template = HTML::Template->new(filename => "header.template");    
    $template->param(%template_variables);
    return $template->output;
}

#
# HTML at bottom of every screen
#
sub page_trailer() {
    my $debugging_info = debugging_info();
    
    return <<eof;
    $debugging_info
    </div>
<body>
</html>
eof
}

#
# Print out information for debugging purposes
#
sub debugging_info() {
    my $params = "";
    foreach my $p (param()) {
        $params .= "param($p)=".param($p)."\n"
    }

    return <<eof;
<hr>
<h4>Debugging information - parameter values supplied to $0</h4>
<pre>
$params
</pre>
<hr>
eof
}


##############################
##############################
##### ANDREW TAYLOR CODE #####
##############################
##############################

# return true if specified string can be used as a login

sub legal_login {
    my ($login) = @_;
    our ($last_error);

    if ($login !~ /^[a-zA-Z][a-zA-Z0-9]*$/) {
        $last_error = "Invalid login '$login': logins must start with a
                       letter and contain only letters and digits.";
        return 0;
    }
    if (length $login < 3 || length $login > 8) {
        $last_error = "Invalid login: logins must be 3-8 characters long.";
        return 0;
    }
    return 1;
}

# return true if specified string can be used as a password

sub legal_password {
    my ($password) = @_;
    our ($last_error);
    
    if ($password =~ /\s/) {
        $last_error = "Invalid password: password can not contain white space.";
        return 0;
    }

    if (length $password < 5) {
        $last_error = "Invalid password: passwords must contain at least 5
                       characters.";
        return 0;
    }

    return 1;
}


# return true if specified string could be an ISBN

sub legal_isbn {
    my ($isbn) = @_;
    our ($last_error);
    
    return 1 if $isbn =~ /^\d{9}(\d|X)$/;
    $last_error = "Invalid isbn '$isbn' : an isbn must be exactly 10 digits.";
    return 0;
}


# return true if specified string could be an credit card number

sub legal_credit_card_number {
    my ($number) = @_;
    our ($last_error);
    
    return 1 if $number =~ /^\d{16}$/;
    $last_error = "Invalid credit card number - must be 16 digits.\n";
    return 0;
}

# return true if specified string could be an credit card expiry date

sub legal_expiry_date {
    my ($expiry_date) = @_;
    our ($last_error);
    
    return 1 if $expiry_date =~ /^\d\d\/\d\d$/;
    $last_error = "Invalid expiry date - must be mm/yy, e.g. 11/04.\n";
    return 0;
}



# return total cost of specified books

sub total_books {
    my @isbns = @_;
    our %book_details;
    my $total = 0;
    foreach my $isbn (@isbns) {
        die "Internal error: unknown isbn $isbn  in total_books" if
!$book_details{$isbn}; # shouldn't happen
        my $price = $book_details{$isbn}{price};
        $price =~ s/[^0-9\.]//g;
        $total += $price;
    }
    return $total;
}

# return true if specified login & password are correct
# user's details are stored in hash user_details

sub authenticate {
    my ($login, $password) = @_;
    our (%user_details, $last_error);
    
    return 0 if !legal_login($login);
    if (not -e "$users_dir/$login") {
        $last_error = "User '$login' does not exist.";
        return 0;
    }

    open(USER, "$users_dir/$login");
    my %details =();
    while (<USER>) {
        next if !/^([^=]+)=(.*)/;
        $details{$1} = $2;
    }
    close(USER);
    foreach my $field (qw(name street city state postcode password)) {
        if (!defined $details{$field}) {
            $last_error = "Incomplete user file: field $field missing";
            return 0;
        }
    }
    if ($details{"password"} ne $password) {
        $last_error = "Incorrect password.";
        return 0;
     }
     %user_details = %details;
     return 1;
}

# read contents of files in the books dir into the hash book
# a list of field names in the order specified in the file 
sub read_books {
    my ($books_file) = @_;
    our %book_details;
    print STDERR "read_books($books_file)\n" if $debug;
    open BOOKS, $books_file or die "Can not open books file '$books_file'\n";
    my $isbn;
    while (<BOOKS>) {
        if (/^\s*"(\d+X?)"\s*:\s*{\s*$/) {
            $isbn = $1;
            next;
        }
        next if !$isbn;
        my ($field, $value);
        if (($field, $value) = /^\s*"([^"]+)"\s*:\s*"(.*)",?\s*$/) {
            $attribute_names{$field}++;
            print STDERR "$isbn $field-> $value\n" if $debug > 1;
            $value =~ s/([^\\]|^)\\"/$1"/g;
            $book_details{$isbn}{$field} = $value;
        } elsif (($field) = /^\s*"([^"]+)"\s*:\s*\[\s*$/) {
            $attribute_names{$1}++;
            my @a = ();
            while (<BOOKS>) {
                last if /^\s*\]\s*,?\s*$/;
                push @a, $1 if /^\s*"(.*)"\s*,?\s*$/;
            }
            $value = join("\n", @a);
            $value =~ s/([^\\]|^)\\"/$1"/g;
            $book_details{$isbn}{$field} = $value;
            print STDERR "book{$isbn}{$field}=@a\n" if $debug > 1;
        }
    }
    close BOOKS;
    $book_read = 1;
}

# return books matching search string

sub search_books {
    my ($search_string) = @_;
    $search_string =~ s/\s*$//;
    $search_string =~ s/^\s*//;
    return search_books1(split /\s+/, $search_string);
}

# return books matching search terms

sub search_books1 {
    my (@search_terms) = @_;
    our %book_details;
    print STDERR "search_books1(@search_terms)\n" if $debug;
    my @unknown_fields = ();
    foreach my $search_term (@search_terms) {
        push @unknown_fields, "'$1'" if $search_term =~ /([^:]+):/ &&
!$attribute_names{$1};
    }
    printf STDERR "$0: warning unknown field%s: @unknown_fields\n",
(@unknown_fields > 1 ? 's' : '') if @unknown_fields;
    my @matches = ();
    BOOK: foreach my $isbn (sort keys %book_details) {
        my $n_matches = 0;
        if (!$book_details{$isbn}{'=default_search='}) {
            $book_details{$isbn}{'=default_search='} =
($book_details{$isbn}{title} || '')."\n".($book_details{$isbn}{authors} || '');
            print STDERR "$isbn default_search ->
'".$book_details{$isbn}{'=default_search='}."'\n" if $debug;
        }
        print STDERR "search_terms=@search_terms\n" if $debug > 1;
        foreach my $search_term (@search_terms) {
            my $search_type = "=default_search=";
            my $term = $search_term;
            if ($search_term =~ /([^:]+):(.*)/) {
                $search_type = $1;
                $term = $2;
            }
            print STDERR "term=$term\n" if $debug > 1;
            while ($term =~ s/<([^">]*)"[^"]*"([^>]*)>/<$1 $2>/g) {}
            $term =~ s/<[^>]+>/ /g;
            next if $term !~ /\w/;
            $term =~ s/^\W+//g;
            $term =~ s/\W+$//g;
            $term =~ s/[^\w\n]+/\\b +\\b/g;
            $term =~ s/^/\\b/g;
            $term =~ s/$/\\b/g;
            next BOOK if !defined $book_details{$isbn}{$search_type};
            print STDERR "search_type=$search_type term=$term
book=$book_details{$isbn}{$search_type}\n" if $debug;
            my $match;
            eval {
                my $field = $book_details{$isbn}{$search_type};
                # remove text that looks like HTML tags (not perfect)
                while ($field =~ s/<([^">]*)"[^"]*"([^>]*)>/<$1 $2>/g) {}
                $field =~ s/<[^>]+>/ /g;
                $field =~ s/[^\w\n]+/ /g;
                $match = $field !~ /$term/i;
            };
            if ($@) {
                $last_error = $@;
                $last_error =~ s/;.*//;
                return (); 
            }
            next BOOK if $match;
            $n_matches++;
        }
        push @matches, $isbn if $n_matches > 0;
    }
    
    sub bySalesRank {
        my $max_sales_rank = 100000000;
        my $s1 = $book_details{$a}{SalesRank} || $max_sales_rank;
        my $s2 = $book_details{$b}{SalesRank} || $max_sales_rank;
        return $a cmp $b if $s1 == $s2;
        return $s1 <=> $s2;
    }
    
    return sort bySalesRank @matches;
}


# return books in specified user's basket

sub read_basket {
    my ($login) = @_;
    our %book_details;
    open F, "$baskets_dir/$login" or return ();
    my @isbns = <F>;

    close(F);
    chomp(@isbns);
    !$book_details{$_} && die "Internal error: unknown isbn $_ in basket\n"
foreach @isbns;
    return @isbns;
}


# delete specified book from specified user's basket
# only first occurance is deleted

sub delete_basket {
    my ($login, $delete_isbn) = @_;
    my @isbns = read_basket($login);
    open F, ">$baskets_dir/$login" or die "Can not open
$baskets_dir/$login: $!";
    foreach my $isbn (@isbns) {
        if ($isbn eq $delete_isbn) {
            $delete_isbn = "";
            next;
        }
        print F "$isbn\n";
    }
    close(F);
    unlink "$baskets_dir/$login" if ! -s "$baskets_dir/$login";
}


# add specified book to specified user's basket

sub add_basket {
    my ($login, $isbn) = @_;
    open F, ">>$baskets_dir/$login" or die "Can not open
$baskets_dir/$login::$! \n";
    print F "$isbn\n";
    close(F);
}


# finalize specified order

sub finalize_order {
    my ($login, $credit_card_number, $expiry_date) = @_;
    my $order_number = 0;

    if (open ORDER_NUMBER, "$orders_dir/NEXT_ORDER_NUMBER") {
        $order_number = <ORDER_NUMBER>;
        chomp $order_number;
        close(ORDER_NUMBER);
    }
    $order_number++ while -r "$orders_dir/$order_number";
    open F, ">$orders_dir/NEXT_ORDER_NUMBER" or die "Can not open
$orders_dir/NEXT_ORDER_NUMBER: $!\n";
    print F ($order_number + 1);
    close(F);

    my @basket_isbns = read_basket($login);
    open ORDER,">$orders_dir/$order_number" or die "Can not open
$orders_dir/$order_number:$! \n";
    print ORDER "order_time=".time()."\n";
    print ORDER "credit_card_number=$credit_card_number\n";
    print ORDER "expiry_date=$expiry_date\n";
    print ORDER join("\n",@basket_isbns)."\n";
    close(ORDER);
    unlink "$baskets_dir/$login";
    
    open F, ">>$orders_dir/$login" or die "Can not open
$orders_dir/$login:$! \n";
    print F "$order_number\n";
    close(F);
    
}


# return order numbers for specified login

sub login_to_orders {
    my ($login) = @_;
    open F, "$orders_dir/$login" or return ();
    my @order_numbers = <F>;
    close(F);
    chomp(@order_numbers);
    return @order_numbers;
}



# return contents of specified order

sub read_order {
    my ($order_number) = @_;
    open F, "$orders_dir/$order_number" or warn "Can not open
$orders_dir/$order_number:$! \n";
    my @lines = <F>;
    close(F);
    chomp @lines;
    foreach (@lines[0..2]) {s/.*=//};
    return @lines;
}

###
### functions below are only for testing from the command line
### Your do not need to use these funtions
###

our $argument;
sub console_main {
    set_global_variables();
    $debug = 1;
    foreach my $dir ($orders_dir,$baskets_dir,$users_dir) {
        if (! -d $dir) {
            print "Creating $dir\n";
            mkdir($dir, 0777) or die("Can not create $dir: $!");
        }
    }
    read_books($books_file);
    my @commands = qw(login new_account search details add drop basket
checkout orders quit);
    my @commands_without_arguments = qw(basket checkout orders quit);
    my $login = "";
    
    print "mekong.com.au - ASCII interface\n";
    while (1) {
        $last_error = "";
        print "> ";
        my $line = <STDIN> || last;
        $line =~ s/^\s*>\s*//;
        $line =~ /^\s*(\S+)\s*(.*)/ || next;
        (my $command, $argument) = ($1, $2);
        $command =~ tr/A-Z/a-z/;
        $argument = "" if !defined $argument;
        $argument =~ s/\s*$//;
        
        if (
            $command !~ /^[a-z_]+$/ ||
            !grep(/^$command$/, @commands) ||
            grep(/^$command$/, @commands_without_arguments) != ($argument
eq "") ||
            ($argument =~ /\s/ && $command ne "search")
        ) {
            chomp $line;
            $line =~ s/\s*$//;
            $line =~ s/^\s*//;
            incorrect_command_message("$line");
            next;
        }

        if ($command eq "quit") {
            print "Thanks for shopping at mekong.com.au.\n";
            last;
        }
        if ($command eq "login") {
            $login = login_command($argument);
            next;
        } elsif ($command eq "new_account") {
            $login = new_account_command($argument);
            next;
        } elsif ($command eq "search") {
            search_command($argument);
            next;
        } elsif ($command eq "details") {
            details_command($argument);
            next;
        }
        
        if (!$login) {
            print "Not logged in.\n";
            next;
        }
        
        if ($command eq "basket") {
            basket_command($login);
        } elsif ($command eq "add") {
            add_command($login, $argument);
        } elsif ($command eq "drop") {
            drop_command($login, $argument);
        } elsif ($command eq "checkout") {
            checkout_command($login);
        } elsif ($command eq "orders") {
            orders_command($login);
        } else {
            warn "internal error: unexpected command $command";
        }
    }
}

sub login_command {
    my ($login) = @_;
    if (!legal_login($login)) {
        print "$last_error\n";
        return "";
    }
    if (!-r "$users_dir/$login") {
        print "User '$login' does not exist.\n";
        return "";
    }
    printf "Enter password: ";
    my $pass = <STDIN>;
    chomp $pass;
    if (!authenticate($login, $pass)) {
        print "$last_error\n";
        return "";
    }
    $login = $login;
    print "Welcome to mekong.com.au, $login.\n";
    return $login;
}

sub new_account_command {
    my ($login) = @_;
    if (!legal_login($login)) {
        print "$last_error\n";
        return "";
    }
    if (-r "$users_dir/$login") {
        print "Invalid user name: login already exists.\n";
        return "";
    }
    if (!open(USER, ">$users_dir/$login")) {
        print "Can not create user file $users_dir/$login: $!";
        return "";
    }
    foreach my $description (@new_account_rows) {
        my ($name, $label)  = split /\|/, $description;
        next if $name eq "login";
        my $value;
        while (1) {
            print "$label ";
            $value = <STDIN>;
            exit 1 if !$value;
            chomp $value;
            if ($name eq "password" && !legal_password($value)) {
                print "$last_error\n";
                next;
            }
            last if $value =~ /\S+/;
        }
        $user_details{$name} = $value;
        print USER "$name=$value\n";
    }
    close(USER);
    print "Welcome to mekong.com.au, $login.\n";
    return $login;
}

sub search_command {
    my ($search_string) = @_;
    $search_string =~ s/\s*$//;
    $search_string =~ s/^\s*//;
    search_command1(split /\s+/, $search_string);
}

sub search_command1 {
    my (@search_terms) = @_;
    my @matching_isbns = search_books1(@search_terms);
    if ($last_error) {
        print "$last_error\n";
    } elsif (@matching_isbns) {
        print_books(@matching_isbns);
    } else {
        print "No books matched.\n";
    }
}

sub details_command {
    my ($isbn) = @_;
    our %book_details;
    if (!legal_isbn($isbn)) {
        print "$last_error\n";
        return;
    }
    if (!$book_details{$isbn}) {
        print "Unknown isbn: $isbn.\n";
        return;
    }
    print_books($isbn);
    foreach my $attribute (sort keys %{$book_details{$isbn}}) {
        next if $attribute =~
/Image|=|^(|price|title|authors|productdescription)$/;
        print "$attribute: $book_details{$isbn}{$attribute}\n";
    }
    my $description = $book_details{$isbn}{productdescription} or return;
    $description =~ s/\s+/ /g;
    $description =~ s/\s*<p>\s*/\n\n/ig;
    while ($description =~ s/<([^">]*)"[^"]*"([^>]*)>/<$1 $2>/g) {}
    $description =~ s/(\s*)<[^>]+>(\s*)/$1 $2/g;
    $description =~ s/^\s*//g;
    $description =~ s/\s*$//g;
    print "$description\n";
}

sub basket_command {
    my ($login) = @_;
    my @basket_isbns = read_basket($login);
    if (!@basket_isbns) {
        print "Your shopping basket is empty.\n";
    } else {
        print_books(@basket_isbns);
        printf "Total: %11s\n", sprintf("\$%.2f", total_books(@basket_isbns));
    }
}

sub add_command {
    my ($login,$isbn) = @_;
    our %book_details;
    if (!legal_isbn($isbn)) {
        print "$last_error\n";
        return;
    }
    if (!$book_details{$isbn}) {
        print "Unknown isbn: $isbn.\n";
        return;
    }
    add_basket($login, $isbn);
}

sub drop_command {
    my ($login,$isbn) = @_;
    my @basket_isbns = read_basket($login);
    if (!legal_isbn($argument)) {
        print "$last_error\n";
        return;
    }
    if (!grep(/^$isbn$/, @basket_isbns)) {
        print "Isbn $isbn not in shopping basket.\n";
        return;
    }
    delete_basket($login, $isbn);
}

sub checkout_command {
    my ($login) = @_;
    my @basket_isbns = read_basket($login);
    if (!@basket_isbns) {
        print "Your shopping basket is empty.\n";
        return;
    }
    print "Shipping
Details:\n$user_details{name}\n$user_details{street}\n$user_details{city}\n$user_details{state},
$user_details{postcode}\n\n";
    print_books(@basket_isbns);
    printf "Total: %11s\n", sprintf("\$%.2f", total_books(@basket_isbns));
    print "\n";
    my ($credit_card_number, $expiry_date);
    while (1) {
            print "Credit Card Number: ";
            $credit_card_number = <>;
            exit 1 if !$credit_card_number;
            $credit_card_number =~ s/\s//g;
            next if !$credit_card_number;
            last if $credit_card_number =~ /^\d{16}$/;
            last if legal_credit_card_number($credit_card_number);
            print "$last_error\n";
    }
    while (1) {
            print "Expiry date (mm/yy): ";
            $expiry_date = <>;
            exit 1 if !$expiry_date;
            $expiry_date =~ s/\s//g;
            next if !$expiry_date;
            last if legal_expiry_date($expiry_date);
            print "$last_error\n";
    }
    finalize_order($login, $credit_card_number, $expiry_date);
}

sub orders_command {
    my ($login) = @_;
    print "\n";
    foreach my $order (login_to_orders($login)) {
        my ($order_time, $credit_card_number, $expiry_date, @isbns) =
read_order($order);
        $order_time = localtime($order_time);
        print "Order #$order - $order_time\n";
        print "Credit Card Number: $credit_card_number (Expiry $expiry_date)\n";
        print_books(@isbns);
        print "\n";
    }
}

# print descriptions of specified books
sub print_books(@) {
    my @isbns = @_;
    print get_book_descriptions(@isbns);
}

# return descriptions of specified books
sub get_book_descriptions {
    my @isbns = @_;
    my $descriptions = "";
    our %book_details;
    foreach my $isbn (@isbns) {
        die "Internal error: unknown isbn $isbn in print_books\n" if
!$book_details{$isbn}; # shouldn't happen
        my $title = $book_details{$isbn}{title} || "";
        my $authors = $book_details{$isbn}{authors} || "";
        $authors =~ s/\n([^\n]*)$/ & $1/g;
        $authors =~ s/\n/, /g;
        $descriptions .= sprintf "%s %7s %s - %s\n", $isbn,
$book_details{$isbn}{price}, $title, $authors;
    }
    return $descriptions;
}

sub set_global_variables {
    $base_dir = ".";
    $books_file = "$base_dir/books.json";
    $orders_dir = "$base_dir/orders";
    $baskets_dir = "$base_dir/baskets";
    $users_dir = "$base_dir/users";
    $last_error = "";
    %user_details = ();
    %book_details = ();
    %attribute_names = ();
    @new_account_rows = (
          'login|Login:|10',
          'password|Password:|10',
          'name|Full Name:|50',
          'street|Street:|50',
          'city|City/Suburb:|25',
          'state|State:|25',
          'postcode|Postcode:|25',
          'email|Email Address:|35'
          );
}


sub incorrect_command_message {
    my ($command) = @_;
    print "Incorrect command: $command.\n";
    print <<eof;
Possible commands are:
login <login-name>
new_account <login-name>                    
search <words>
details <isbn>
add <isbn>
drop <isbn>
basket
checkout
orders
quit
eof
}


