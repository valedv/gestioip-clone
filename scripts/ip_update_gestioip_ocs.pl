#!/usr/bin/perl -w


# Copyright (C) 2011 Marc Uebel

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# ip_update_gestioip_ocs.pl Version 2.2.8.2

# script para actualizar la BBDD del sistema GestioIP against an OCS Inventory NG
# tested with OCS v1.01 and v1.02.3

# This scripts synchronizes only the networks of GestioIP with marked "sync"-field 
# see documentation for further information (www.gestioip.net)

# Usage: ./ip_update_gestioip_ocs.pl --help

# execute it from cron. Example crontab:
# 30 10 * * * /usr/share/gestioip/bin/ip_update_gestioip_ocs.pl -o -m > /dev/null 2>&1



use strict;
use Getopt::Long;
Getopt::Long::Configure ("no_ignore_case");
use DBI;
use Time::Local;
use Time::HiRes qw(sleep);
use Date::Calc qw(Add_Delta_Days); 
use Date::Manip qw(UnixDate);
use Net::IP;
use Net::IP qw(:PROC);
use Net::Ping::External qw(ping);
use Mail::Mailer;
use Socket;
use Parallel::ForkManager;
use FindBin qw($Bin);
use Fcntl qw(:flock);
use Net::DNS;

my $VERSION="2.2.8.1";


my $dir = $Bin;

$dir =~ /^(.*)\/bin/;
my $base_dir=$1;

my $config_name="ip_update_gestioip.conf";

# my $dir = "/apsolute/path/to/$config_name";

if ( ! -r "${base_dir}/etc/${config_name}" ) {
        print "\nCan't find configuration file \"$config_name\"\n";
        print "\n\"$dir/$config_name\" doesn't exists\n";
        exit 1;
}

my $conf = $base_dir . "/etc/" . $config_name;

my ( $update_ocs, $update_dns, $update_all, $verbose, $log, $mail, $help, $disable_audit, $version_arg );

GetOptions(
	"verbose!"=>\$verbose,
	"Version!"=>\$version_arg,
	"log=s"=>\$log,
	"disable_audit!"=>\$disable_audit,
	"mail!"=>\$mail,
	"help!"=>\$help
) or print_help();

if ( $help ) { print_help(); }
if ( $version_arg ) { print_version(); }

my $enable_audit = "1";
$enable_audit = "0" if $disable_audit;




my %params;

open(VARS,"<$conf") or die "Can no open $conf: $!\n";
while (<VARS>) {
	chomp;
	s/#.*//;
	s/^\s+//;
	s/\s+$//;
	next unless length;
	my ($var, $value) = split(/\s*=\s*/, $_, 2);
	$params{$var} = $value;
}
close VARS;

my $client_name_conf = $params{client};

my $lockfile = $base_dir . "/var/run/" . $client_name_conf . "_ip_update_gestioip_dns.lock";

no strict 'refs';
open($lockfile, '<', $0) or die("Unable to create lock file: $!\n");
use strict;

unless (flock($lockfile, LOCK_EX|LOCK_NB)) {
	print "$0 is already running. Exiting.\n";
	exit(1);
}

my $gip_version=get_version();

if ( $VERSION !~ /$gip_version/ ) {
	print "Script and GestioIP version are not compatible\n\nGestioIP version: $gip_version - script version: $VERSION\n\n";
	exit;
}

my $lang=$params{lang} || "en";
my $vars_file=$base_dir . "/etc/vars/vars_update_gestioip_" . "$lang";

my $set_ut_ocs=$params{set_update_type_to_ocs};
$set_ut_ocs = "no" if $set_ut_ocs ne "yes";

my %lang_vars;

open(LANGVARS,"<$vars_file") or die "Can no open $vars_file: $!\n";
while (<LANGVARS>) {
	chomp;
	s/#.*//;
	s/^\s+//;
	s/\s+$//;
	next unless length;
	my ($var, $value) = split(/\s*=\s*/, $_, 2);
	$lang_vars{$var} = $value;
}
close LANGVARS;


my $client_count = count_clients();
my $client_id;
if ( $client_count == "1" ) {
        my $one_client_name = check_one_client_name("$client_name_conf") || "";
        if ( $one_client_name eq $client_name_conf || $client_name_conf eq "DEFAULT" ) {
                $client_id=get_client_id_one() || "";
        }
} else {
        $client_id=get_client_id_from_name("$client_name_conf") || "";
}

if ( ! $client_id ) {
        print "$client_name_conf: $lang_vars{client_not_found_message} $conf\n";
        exit 1;
}

my $logdir="$params{logdir}" if ( ! $log );

my $logfile_name;
if ( $client_count == "1" ) {
        $logfile_name = "ip_update_gestioip_dns.log";
} else {
        $logfile_name = $client_name_conf . "_ip_update_gestioip_dns.log";
}


if ( ! -d $logdir ) {
        print "$lang_vars{logdir_not_found_message}: $logdir - using $log\n";
        $log=$base_dir . "/var/log/" . $logfile_name;
} else {
        $log=$logdir . "/" . $logfile_name;
}


#my $no_ping_redes="$params{no_ping_redes}" || "";
my $no_ocs_redes="$params{no_ocs_redes}" || "";
my $ignorar = "";
$ignorar = $params{'ignorar'} if $params{'ignorar'};
$ignorar =~ s/,/|/g;
my $generic_dyn_host_name = $params{'generic_dyn_host_name'} if $params{'generic_dyn_host_name'};
$generic_dyn_host_name =~ s/,/|/g if $params{'generic_dyn_host_name'};
$generic_dyn_host_name = "_NO_GENERIC_DYN_NAME_GIVEN_" if ! $params{'generic_dyn_host_name'};

my $mail_destinatarios = \$params{mail_destinatarios};
my $mail_from = \$params{mail_from};

my ($s, $mm, $h, $d, $m, $y) = (localtime) [0,1,2,3,4,5];
$m++;
$y+=1900;
if ( $d =~ /^\d$/ ) { $d = "0$d"; }
if ( $s =~ /^\d$/ ) { $s = "0$s"; }
if ( $m =~ /^\d$/ ) { $m = "0$m"; }
if ( $mm =~ /^\d$/ ) { $mm = "0$mm"; }
my $mydatetime = "$y-$m-$d $h:$mm:$s";
my $myunixtime = time();


open(LOG,">$log") or die "$log: $!\n";


my ( $count_entradas_ocs, $count_entradas_dns );
my $vigilada_found = "0";


my @values_ocs=get_ip_ocs();
my $end=@values_ocs;

my $audit_type="24";
my $audit_class="2";
my $update_type_audit="5";
my $descr_audit;
my $event="---";
insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";


my %vigilada_redes = get_vigilada_redes_hash("$client_id");
my $vigilada_redes_scal = %vigilada_redes;
$vigilada_found = "1" if ! $vigilada_redes_scal;


my @client_entries=get_client_entries("$client_id");
my $default_resolver = $client_entries[0]->[20];
my @dns_servers =("$client_entries[0]->[21]","$client_entries[0]->[22]","$client_entries[0]->[23]");

my $res_dns;
my $dns_error = "";
if ( $default_resolver eq "yes" ) {
        $res_dns = Net::DNS::Resolver->new;
} else {
        $res_dns = Net::DNS::Resolver->new(
        udp_timeout => 5,
        nameservers => [@dns_servers],
        recurse     => 1,
        debug       => 1,
        );
}

$res_dns->retry(2);
$res_dns->udp_timeout(10);
my $used_nameservers = $res_dns->nameservers;

my $all_used_nameservers = join (" ",$res_dns->nameserver());

if ( $used_nameservers eq "0" ) {
        print "$lang_vars{no_dns_server_message}\n\n";
        exit 1;
}

if ( $all_used_nameservers eq "127.0.0.1" && $default_resolver eq "yes" ) {
	print "$lang_vars{no_answer_from_dns_message} - $lang_vars{nameserver_localhost_message}\n\n$lang_vars{exiting_message}\n\n";

}


$count_entradas_ocs=0;
my $i = "0";

my @values_ocs_new;
my $k=0;
my $l=0;
my $old_time = 0;
my $old_ip_ocs = "0.0.0.1";
my $sinc_red_found = 1;
my $valid_host_entry_found = 1;
foreach ( @values_ocs ) {
	if ( ! $values_ocs[$k]->[0] || ! $values_ocs[$k]->[1] || ! $values_ocs[$k]->[2] || ! $values_ocs[$k]->[3] || ! $values_ocs[$k]->[4] ) {
		$k++;
		next;
	}
	if ( ! $vigilada_redes{"$values_ocs[$k]->[1]"} ) {
		$k++;
		next;
	}
	if ( $vigilada_redes{"$values_ocs[$k]->[1]"} eq "n" ) {
		$k++;
		next;
	} else {
		$sinc_red_found = 0;
	}
	if ( $values_ocs[$k]->[0] eq "0.0.0.0" || $values_ocs[$k]->[0] !~ /\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/ ) {
		$k++;
		next;
	}
	
	$valid_host_entry_found = 0;

	my ( $year, $month, $day, $hour, $min, $sec ) = UnixDate($values_ocs[$k]->[4], "%Y", "%m", "%d", "%H", "%M", "%S");
	$month = $month - 1;
	$year=$year-1900;
	my $time = timelocal($sec, $min, $hour, $day, $month, $year);

	if ( $l > 0 ) {
		my @values_red=get_red_ocs("$client_id","$values_ocs[$k]->[1]");
		my $red_num = $values_red[0]->[0];
		my @reserved_ranges_found;
		if ( $params{dyn_rangos_only} eq "yes" ) {
			@reserved_ranges_found=check_for_reserved_range("$client_id","$red_num");
		}
		if ( ! $reserved_ranges_found[0] && $params{dyn_rangos_only} eq "yes" ) {
			$k++;
			next;
		}

		my $range_member = "0";
		if ( $reserved_ranges_found[0] && $params{dyn_rangos_only} eq "yes" ) {
			my $ip_int_range_check = ip_to_int("$values_ocs[$k]->[0]");
			foreach ( @reserved_ranges_found ) {
				if ( $ip_int_range_check < $_->[1] || $ip_int_range_check > $_->[2] ) {
					next;
				} else {
					$range_member="1";
					last;
				}
			}
		}

		if ( $range_member ==  "0" && $params{dyn_rangos_only} eq "yes" ) {
			$k++;
			next;
		}


		if ( "$values_ocs[$k]->[0]" eq "$old_ip_ocs" && $time > $old_time ) {
			push (@values_ocs_new, $values_ocs[$k]);
			$values_ocs_new[-1]->[4] = $time;
		} elsif ( "$values_ocs[$k]->[0]" eq "$old_ip_ocs" && $time <= $old_time ) {
			$k++;
			next;
		} else {
			push (@values_ocs_new, $values_ocs[$k]);
			$values_ocs_new[-1]->[4] = $time;
		}
	} else {
		push (@values_ocs_new, $values_ocs[$k]);
		$values_ocs_new[-1]->[4] = $time;
		$l++;
	}


	$old_time = $time;
	$old_ip_ocs = $values_ocs[$k]->[0];
	$k++;
}

if ( $sinc_red_found == 1 ) {
	print LOG "\n--- $lang_vars{no_sync_redes_ocs} ---\n";
	print "\n--- $lang_vars{no_sync_redes_ocs} ---\n";
	print "\n--- $lang_vars{mark_red_explic_message} ---\n\n";
	exit 1;
}
if ( $valid_host_entry_found == 1 ) {
	print LOG "\n--- $lang_vars{no_ocs_host_found} ---\n";
	print "\n--- $lang_vars{no_ocs_host_found} ---\n\n";
}


@values_ocs = @values_ocs_new;


my ( %res_sub, %res, %result);
my ( $ip_ad, $pm, $pid, $ip );

my $MAX_PROCESSES=$params{max_sinc_procs} || "254";
$pm = new Parallel::ForkManager($MAX_PROCESSES);

$pm->run_on_finish(
	sub { my ($pid, $exit_code, $ident) = @_;
		$res_sub{$pid}=$exit_code;
	}
);
$pm->run_on_start(
	sub { my ($pid,$ident)=@_;
		$res{$pid}="$ident";
	}
);


foreach ( @values_ocs ) {

	$count_entradas_ocs++;
	my $exit;

	$ip_ad=$values_ocs[$i++]->[0];
	
		##fork
		$pid = $pm->start("$ip_ad") and next;
			#child
			my $p = ping(host => "$ip_ad", timeout => 2);
			if ( $p ) {
				$exit=0;
			} else {
				$exit=1;
			}


			my ($ptr_query,$dns_result_ip);

			if ( $default_resolver eq "yes" ) {
				$res_dns = Net::DNS::Resolver->new;
			} else {
				$res_dns = Net::DNS::Resolver->new(
					nameservers => [@dns_servers],
					recurse     => 1,
					debug       => 0,
				);
			}

			$res_dns->udp_timeout(10);

			if ( $ip_ad =~ /\w+/ ) {
				$ptr_query = $res_dns->search("$ip_ad");

				if ($ptr_query) {
					foreach my $rr ($ptr_query->answer) {
						next unless $rr->type eq "PTR";
						$dns_result_ip = $rr->ptrdname;
					}
				} else {
					$dns_error = $res_dns->errorstring;
				}
			}


			if ( $dns_error =~ /(query timed out|no nameservers)/ ) {
				exit 5;
			} else {
				if ( $dns_result_ip && $exit == 0 ) {
					$exit=2;
				} elsif ( $dns_result_ip && $exit == 1 ) {
					$exit=3;
				} elsif ( ! $dns_result_ip && $exit == 0 ) {
					$exit=4;

				}
			}


		$pm->finish($exit); # Terminates the child process

}


$pm->wait_all_children;


while (($pid,$ip) = each ( %res )) {
	$result{$ip}=$res_sub{$pid};
}


print LOG "####### Synchronization against the OCS ($mydatetime) #######\n\n";

my ($hostname_ip,$update_type, $ip_ocs, $ip_ocs_int, $red_ocs, $hostname_ocs, $mask, $descr_ip, $cat_ip, $comentario_ip,$loc_ip,$hostname_ip_audit);
my @reserved_ranges_found;
for ( $i=0; $i < $end; $i++ ) {

	if ( ! $values_ocs[$i+1] ) { last; }

	if ( $no_ocs_redes =~ /$values_ocs[$i]->[1]/ ) { next; }
	$count_entradas_ocs++;
	$values_ocs[$i]->[0] =~ /(^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*/;
	$ip_ocs=$1;
	$ip_ocs_int = ip_to_int($ip_ocs);
	$values_ocs[$i]->[1] =~ /(^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*/;
	$red_ocs=$1;
	$values_ocs[$i]->[2] =~ /(^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*/;
	$mask=$1;
	$red_ocs=$values_ocs[$i]->[1];
	$hostname_ocs="$values_ocs[$i]->[3]";
	my $last_update_ocs="$values_ocs[$i]->[4]";


	my $exit=$result{$ip_ocs};

	my $ping_result=0;  # (not OK)
	$ping_result=1 if $exit == "0" || $exit == "2" || $exit == "4";

	my $ignor_reason=0; # 1: no dns entry; 2: generic auto name; 3: hostname matches ignore-string
	my @dns_result_ip;
	my $hostname;
	if ( $exit == 2 || $exit == 3 ) {

		my ($ptr_query,$dns_result_ip);

		if ( $default_resolver eq "yes" ) {
			$res_dns = Net::DNS::Resolver->new;
		} else {

			$res_dns = Net::DNS::Resolver->new(
				nameservers => [@dns_servers],
				recurse     => 1,
				debug       => 0,
			);
		}

		$res_dns->udp_timeout(10);

		if ( $ip_ad =~ /\w+/ ) {
			$ptr_query = $res_dns->search("$ip_ad");

			if ($ptr_query) {
				foreach my $rr ($ptr_query->answer) {
					next unless $rr->type eq "PTR";
					$dns_result_ip = $rr->ptrdname;
				}
			} else {
				$dns_error = $res_dns->errorstring;
			}
		}


		$hostname = $dns_result_ip || "unknown";

		if ( $hostname eq "unknown" ) {
			$ignor_reason=1;
		}
	} else {
		$hostname = "unknown";
		$ignor_reason=1;
	}

	my $ptr_name = $ip_ocs;
	$ptr_name =~ /(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/;
	my $generic_auto = "$2-$3-$4|$4-$3-$2";

	
	my @values_ip=();
	my @values_red=();
	@values_ip=get_host_ip("$client_id",$ip_ocs_int);
	@values_red=get_red_ocs("$client_id",$values_ocs[$i]->[1]);

	my $red_num = $values_red[0]->[0];

#	if ( $params{dyn_rangos_only} eq "yes" ) {
#		@reserved_ranges_found=check_for_reserved_range("$red_num");
#	}
#	if ( ! $reserved_ranges_found[0] && $params{dyn_rangos_only} eq "yes" ) {
#		next;
#	}

	my $red_loc = $values_red[0]->[1] || "-1";
	my $update_type_name;
	my $update_type_ocs=get_update_type("ocs");
	my $range = "-1";
	if ( $values_ip[0]->[0] ) {
		$hostname_ip=$values_ip[0]->[1];
		$hostname_ip_audit = $hostname_ip || "---";
		$update_type=$values_ip[0]->[2] || "$update_type_ocs";
		$update_type_name=get_update_type_name("$update_type");
		$range = $values_ip[0]->[4] || "-1";
		$descr_ip = $values_ip[0]->[5] || "NULL";
		$descr_ip = "---" if $descr_ip eq "NULL";
		$loc_ip = $values_ip[0]->[6] || "NULL";
		$loc_ip = "---" if $loc_ip eq "NULL";
		$cat_ip = $values_ip[0]->[7] || "NULL";
		$cat_ip = "---" if $cat_ip eq "NULL";
		$comentario_ip = $values_ip[0]->[8] || "NULL";
		$comentario_ip = "---" if $comentario_ip eq "NULL";
	} else {
		$hostname_ip="";
		$hostname_ip_audit = $hostname_ip || "---";
		$update_type="$update_type_ocs";
		$update_type_name="unknown";
		$range = "-1";
		$descr_ip = "---";
		$loc_ip = "---";
		$cat_ip = "---";
		$comentario_ip = "---";
	}



	# delete entry if host doesn't ansers to ping AND update_type not "man" AND $params{delete_ocs_hosts_down_all} eq "yes"
	if ( $ping_result == "0" && $update_type_name ne "man" && $params{delete_ocs_hosts_down_all} eq "yes") {
		my $audit_type="14";
		my $audit_class="1";
		my $update_type_audit="5";
		if ( $range == "-1" ) {
			my $event="$ip_ocs: $hostname_ip_audit,$descr_ip,$loc_ip,$cat_ip,$comentario_ip";
			my $host_id=get_host_id_from_ip_int("$client_id","$ip_ocs_int");
			delete_custom_host_column_entry("$client_id","$host_id");
			drop_host_ocs("$client_id","$ip_ocs_int","$ip_ocs","$hostname_ip","$audit_type","$audit_class","$update_type_audit","$event","$vars_file","$lang_vars{no_ping_message}");
		} else {
			my $event="$ip_ocs: $hostname_ip_audit,$descr_ip,$loc_ip,$cat_ip,$comentario_ip";
			my $host_id=get_host_id_from_ip_int("$client_id","$ip_ocs_int");
			delete_custom_host_column_entry("$client_id","$host_id");
			drop_host_ocs_range("$client_id","$ip_ocs_int","$ip_ocs","$hostname_ip","$audit_type","$audit_class","$update_type_audit","$event","$vars_file","$lang_vars{no_ping_message}");
		}
		next;
	}



	# delete entry if host matches generic_dyn_host_name AND don't ansers to ping AND update_type not "man" AND $params{delete_ocs_hosts_down_match}} eq "yes"
	if ( $hostname_ocs =~ /$generic_dyn_host_name/ && $ping_result == "0" && $update_type_name ne "man" && $params{delete_ocs_hosts_down_match} eq "yes") {
		my $audit_type="14";
		my $audit_class="1";
		my $update_type_audit="5";
		if ( $range == "-1" ) {
			my $event="$ip_ocs: $hostname_ip_audit,$descr_ip,$loc_ip,$cat_ip,$comentario_ip";
			my $host_id=get_host_id_from_ip_int("$client_id","$ip_ocs_int");
			delete_custom_host_column_entry("$client_id","$host_id");
			drop_host_ocs("$client_id","$ip_ocs_int","$ip_ocs","$hostname_ip","$audit_type","$audit_class","$update_type_audit","$event","$vars_file","$lang_vars{tiene_man_string_no_ping_message} (OCS: $hostname_ocs)");
		} else {
			my $event="$ip_ocs: $hostname_ip_audit,$descr_ip,$loc_ip,$cat_ip,$comentario_ip";
			my $host_id=get_host_id_from_ip_int("$client_id","$ip_ocs_int");
			delete_custom_host_column_entry("$client_id","$host_id");
			drop_host_ocs_range("$client_id","$ip_ocs_int","$ip_ocs","$hostname_ip","$audit_type","$audit_class","$update_type_audit","$event","$vars_file","$lang_vars{tiene_man_string_no_ping_message} (OCS: $hostname_ocs)");
		}
		next;
	}


	# delete entry if host matches generic_auto AND doesn't ansers to ping AND update_type not "man" AND $params{delete_ocs_hosts_down_match} eq "yes"
	if ( $hostname =~ /$generic_auto/ && $ping_result == "0" && $update_type_name ne "man" && $params{delete_ocs_hosts_down_match} eq "yes") {
		my $audit_type="14";
		my $audit_class="1";
		my $update_type_audit="5";
		if ( $range == "-1" ) {
			my $event="$ip_ocs: $hostname_ip_audit,$descr_ip,$loc_ip,$cat_ip,$comentario_ip";
			my $host_id=get_host_id_from_ip_int("$client_id","$ip_ocs_int");
			delete_custom_host_column_entry("$client_id","$host_id");
			drop_host_ocs("$client_id","$ip_ocs_int","$ip_ocs","$hostname_ip","$audit_type","$audit_class","$update_type_audit","$event","$vars_file","$lang_vars{tiene_string_no_ping_message}");
		} else {
			my $event="$ip_ocs: $hostname_ip_audit,$descr_ip,$loc_ip,$cat_ip,$comentario_ip";
			my $host_id=get_host_id_from_ip_int("$client_id","$ip_ocs_int");
			delete_custom_host_column_entry("$client_id","$host_id");
			drop_host_ocs_range("$client_id","$ip_ocs_int","$ip_ocs","$hostname_ip","$audit_type","$audit_class","$update_type_audit","$event","$vars_file","$lang_vars{tiene_string_no_ping_message}");
		}
		next;
	}


	# no responde to ping and $params{ignore_ocs_host_down} eq "yes": ignore
	if ( $params{ignore_ocs_host_down} eq "yes" && $ping_result == "0" ) {
		if ( $hostname_ip ) {
			update_host_ping_info("$client_id","$ip_ocs_int","$ping_result");
		}
		print LOG "$ip_ocs: $lang_vars{no_ping_message} - $lang_vars{ignorado_message}\n";
		print "$ip_ocs: $lang_vars{no_ping_message} - $lang_vars{ignorado_message}\n" if $verbose;
		next;
	}

	# no responde to ping and dns->generic_auto_name: ignore
	if ( $hostname =~ /$generic_auto/ && $params{ignore_generic_auto} eq "yes" && $ping_result == "0" ) {
		if ( $hostname_ip ) {
			update_host_ping_info("$client_id","$ip_ocs_int","$ping_result");
		}
		print LOG "$ip_ocs: $lang_vars{tiene_string_no_ping_message} - $lang_vars{ignorado_message}\n";
		print "$ip_ocs: $lang_vars{tiene_string_no_ping_message} - $lang_vars{ignorado_message}\n" if $verbose;
		next;
	}

	# no responde to ping and dns matches "ignorar" value: ignore
	if ( $hostname =~ /$ignorar/ && $ping_result == "0" ) {
		if ( $hostname_ip ) {
			update_host_ping_info("$client_id","$ip_ocs_int","$ping_result");
		}
		print "$ip_ocs: $lang_vars{tiene_string_no_ping_message} - $lang_vars{ignorado_message}\n" if $verbose;
		print LOG "$ip_ocs: $lang_vars{tiene_string_no_ping_message} - $lang_vars{ignorado_message}\n";
		next;
	}


	if ( $ip_ocs ne $values_ocs[$i+1]->[0] ) {
		if ( ! $hostname_ip && $range == "-1" ) {
			print LOG "$ip_ocs: $lang_vars{host_anadido_message}: $hostname_ocs\n";
			print "$ip_ocs: $lang_vars{host_anadido_message}: $hostname_ocs\n" if $verbose;
			insert_host("$client_id",$red_num,$red_loc,$hostname_ocs, $ip_ocs_int,$last_update_ocs,$update_type,$ping_result);

			my $audit_type="15";
			my $audit_class="1";
			my $update_type_audit="5";
			my $host_descr_audit = "---";
			my $comentario_audit = "---";
			my $loc_audit=$red_loc;
			$loc_audit= "---" if $red_loc eq "-1";
			my $audit_cat = "---";
			my $event="$ip_ocs,$hostname_ocs,$host_descr_audit,$loc_audit,$audit_cat,$comentario_audit";
			insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";

		} elsif ( ! $hostname_ip && $range != "-1" ) {
			print LOG "$ip_ocs: $lang_vars{host_anadido_message}: $hostname_ocs\n";
			print "$ip_ocs: $lang_vars{host_anadido_message}: $hostname_ocs\n" if $verbose;
			update_host_ocs("$client_id",$hostname_ocs, $ip_ocs_int,$last_update_ocs,$ping_result);

			my $audit_type="15";
			my $audit_class="1";
			my $update_type_audit="5";
			my $host_descr_audit = "---";
			my $comentario_audit = "---";
			my $loc_audit=$red_loc;
			$loc_audit= "---" if $red_loc eq "-1";
			my $audit_cat = "---";
			my $event="$ip_ocs,$hostname_ocs,$host_descr_audit,$loc_audit,$audit_cat,$comentario_audit";
			insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";

		} elsif ( $hostname_ip =~ /$hostname_ocs/i ) {
			print LOG "$ip_ocs: $lang_vars{tiene_entrada_message}: $hostname_ocs - $lang_vars{ignorado_message}\n";
			print "$ip_ocs: $lang_vars{tiene_entrada_message}: $hostname_ocs - $lang_vars{ignorado_message}\n" if $verbose;
		} else {
			if ( $update_type_name eq "dns" ) {
				print LOG "$ip_ocs: $lang_vars{hostname_no_match_message} (BBDD:$hostname_ip_audit/OCS:$hostname_ocs) - $lang_vars{entrada_actualizada_message}: $hostname_ocs (ultimo update por: $update_type_name)\n";
				print "$ip_ocs: $lang_vars{hostname_no_match_message} (BBDD:$hostname_ip_audit/OCS:$hostname_ocs) - $lang_vars{entrada_actualizada_message}: $hostname_ocs (ultimo update por: $update_type_name)\n" if $verbose;
				update_host_ocs("$client_id",$hostname_ocs,$ip_ocs_int,$last_update_ocs,$ping_result);	

				my $audit_type="1";
				my $audit_class="1";
				my $update_type_audit="5";
				my $event="$ip_ocs: $hostname_ip_audit -> $hostname_ocs";
				insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
			} elsif ( $update_type_name eq "man" ) {
				 print LOG "$ip_ocs: $lang_vars{hostname_no_match_message} (BBDD:$hostname_ip_audit/OCS:$hostname_ocs) - $lang_vars{ignorado_message} (ultimo update por: $update_type_name)\n";
				 print "$ip_ocs: $lang_vars{hostname_no_match_message} (BBDD:$hostname_ip_audit/OCS:$hostname_ocs) - $lang_vars{ignorado_message} (ultimo update por: $update_type_name)\n" if $verbose;
			} elsif ( $update_type_name eq "ocs" ) {
				print LOG "$ip_ocs: $lang_vars{hostname_no_match_message} (BBDD:$hostname_ip_audit/OCS:$hostname_ocs) -  $lang_vars{entrada_actualizada_message}: $hostname_ocs (ultimo update por: $update_type_name)\n";
				print "$ip_ocs: $lang_vars{hostname_no_match_message} (BBDD:$hostname_ip_audit/OCS:$hostname_ocs) -  $lang_vars{entrada_actualizada_message}: $hostname_ocs (ultimo update por: $update_type_name)\n" if $verbose;

				my $audit_type="1";
				my $audit_class="1";
				my $update_type_audit="5";
				my $event="$ip_ocs: $hostname_ip_audit -> $hostname_ocs";
				insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
				update_host_ocs("$client_id",$hostname_ocs,$ip_ocs_int,$last_update_ocs,$ping_result);
			} else {
				print LOG "$ip_ocs:  $lang_vars{hostname_no_match_message} (BBDD:$hostname_ip_audit/OCS:$hostname_ocs) - $lang_vars{entrada_actualizada_message}: $hostname_ocs (ultimo update por: unknown)\n";
				print "$ip_ocs:  $lang_vars{hostname_no_match_message} (BBDD:$hostname_ip_audit/OCS:$hostname_ocs) - $lang_vars{entrada_actualizada_message}: $hostname_ocs (ultimo update por: unknown)\n" if $verbose;
				update_host_ocs("$client_id",$hostname_ocs,$ip_ocs_int,$last_update_ocs,$ping_result);

				my $audit_type="1";
				my $audit_class="1";
				my $update_type_audit="5";
				my $event="$ip_ocs: $hostname_ip_audit -> $hostname_ocs";
				insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
			}
		}
	}
}



close LOG;

$count_entradas_ocs ||= "0";
$count_entradas_dns ||= "0";

if ( $vigilada_found == "1" ) {
	print LOG "\n--- $lang_vars{no_sync_redes} ---\n";
	print "\n--- $lang_vars{no_sync_redes} ---\n\n";
	print "\n$lang_vars{mark_red_message}\n";
}


my $count_entradas = $count_entradas_ocs + $count_entradas_dns;

send_mail() if $mail;


##############################

sub get_ip_ocs {
	my $ip_ref;
	my @values_ocs;
	my $dbh = mysql_connection_ocs();
	my $sth = $dbh->prepare("select n.IPADDRESS,n.IPSUBNET,n.IPMASK,h.name,h.LASTDATE from networks n, hardware h where n.hardware_id = h.id and h.LASTDATE >= '2008-01-29' order by inet_aton(n.IPADDRESS);");
	$sth->execute() or die "error while prepareing query: $DBI::errstr\n";
	while ( $ip_ref = $sth->fetchrow_arrayref ) {
	push @values_ocs, [ @$ip_ref ];
	}
	$dbh->disconnect;
	return @values_ocs;
}

#sub get_vigilada_red {
#	my ( $client_id,$red ) = @_;
#	my $vigilada_red;
#	my $dbh = mysql_connection_gestioip();
#	my $sth = $dbh->prepare("SELECT vigilada FROM net where red=\"$red\"
#			") or print "Fehler bei select: $DBI::errstr\n";
#	$sth->execute();
#	$vigilada_red = $sth->fetchrow_array;
#	$sth->finish();
#	$dbh->disconnect;
#	return $vigilada_red;
#}

sub get_red_ocs {
	my ( $client_id,$red ) = @_;
	my $ip_ref;
	my @values_red;
	my $dbh = mysql_connection_gestioip();
	my $sth = $dbh->prepare("SELECT red_num, loc FROM net WHERE red=\"$red\" AND client_id = \"$client_id\"");
	$sth->execute() or print "error while prepareing query: $DBI::errstr\n";
	while ( $ip_ref = $sth->fetchrow_arrayref ) {
	push @values_red, [ @$ip_ref ];
	}
	$sth->finish();
	$dbh->disconnect;
	return @values_red;
}


sub drop_host_ocs {
	my ( $client_id,$ip_ocs_int,$ip_ocs,$hostname_ip,$audit_type,$audit_class,$update_type_audit,$event,$vars_file,$message ) = @_;
	my $dbh = mysql_connection_gestioip();
	my $sth;
	my $deleted;
	if ($ip_ocs) {
		$sth = $dbh->prepare("DELETE FROM host WHERE ip=\"$ip_ocs_int\" AND client_id = \"$client_id\""
					) or die "Error insert db: $DBI::errstr\n";
		$deleted=$sth->execute() or die "Fehler bei execute db: $DBI::errstr\n";
		if ( $deleted == "1" ) {
			print LOG "$ip_ocs: $message - $lang_vars{entrada_borrado_message}: $hostname_ip\n";
			print "$ip_ocs: $message - $lang_vars{entrada_borrado_message}: $hostname_ip\n" if $verbose;
			insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
		}
	}
	$sth->finish();
        $dbh->disconnect;

}

sub drop_host_ocs_range {
	my ( $client_id,$ip_ocs_int,$ip_ocs,$hostname_ip,$audit_type,$audit_class,$update_type_audit,$event,$vars_file,$message ) = @_;
        my $dbh = mysql_connection_gestioip();
        my $qip_ocs_int = $dbh->quote( $ip_ocs_int );

        my $sth = $dbh->prepare("UPDATE host SET hostname='', host_descr='', int_admin='n', alive='', last_response='' WHERE ip = \"$qip_ocs_int\" AND ( hostname != '' || hostname != 'NULL' AND client_id = \"$client_id\" )"
                                ) or die "Can not execute statement: $dbh->errstr";
        my $deleted = $sth->execute() or die "Can not execute statement: $dbh->errstr";
	if ( $deleted == "1" ) {
		print LOG "$ip_ocs: $message - $lang_vars{entrada_borrado_message}: $hostname_ip\n";
		print "$ip_ocs: $message - $lang_vars{entrada_borrado_message}: $hostname_ip\n" if $verbose;
		insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
	}
        $sth->finish();
        $dbh->disconnect;
}


sub insert_host {
	my ( $client_id,$red_num, $red_loc, $hostname_ocs, $ip_ocs_int, $last_update_ocs, $update_type, $alive ) = @_;
	my $last_response = time();
	my $dbh = mysql_connection_gestioip();
	my $sth;
	if ( $set_ut_ocs eq "yes" ) {
		$sth = $dbh->prepare("INSERT INTO host (ip,hostname,loc,categoria,red_num,int_admin,update_type,last_update,alive,last_response,$client_id) values (\"$ip_ocs_int\",\"$hostname_ocs\",\"$red_loc\",'-1'\"$red_num\",\"n\",\"$update_type\",\"$last_update_ocs\",\"$alive\",\"$last_response\",\"$client_id\")"
				) or die "Fehler bei insert db: $DBI::errstr\n";
	} else {
		$sth = $dbh->prepare("INSERT INTO host (ip,hostname,loc,categoria,red_num,int_admin,update_type,last_update,alive,last_response,client_id) values (\"$ip_ocs_int\",\"$hostname_ocs\",\"$red_loc\",'-1',\"$red_num\",\"n\",\"-1\",\"$last_update_ocs\",\"$alive\",\"$last_response\",\"$client_id\")"
				) or die "Fehler bei insert db: $DBI::errstr\n";
	}
	$sth->execute() or die "Fehler bei execute db: $DBI::errstr\n";
        $sth->finish();
        $dbh->disconnect;
}

sub update_host_ocs {
	my ( $client_id,$hostname_ocs, $ip_ocs_int, $last_update_ocs, $alive ) = @_;
	my $last_response = time();
        my $dbh = mysql_connection_gestioip();
	my $sth;
	if ( $set_ut_ocs eq "yes" ) {
        	$sth = $dbh->prepare("UPDATE host SET hostname=\"$hostname_ocs\", update_type=(select id from update_type where type=\"ocs\"), last_update=\"$last_update_ocs\", alive=\"$alive\", last_response=\"$last_response\" WHERE ip=\"$ip_ocs_int\" AND client_id = \"$client_id\""
                                ) or die "Fehler bei insert db: $DBI::errstr\n";
	} else {
        	$sth = $dbh->prepare("UPDATE host SET hostname=\"$hostname_ocs\", last_update=\"$last_update_ocs\", alive=\"$alive\", last_response=\"$last_response\" WHERE ip=\"$ip_ocs_int\" AND client_id = \"$client_id\""
                                ) or die "Fehler bei insert db: $DBI::errstr\n";
	}
        $sth->execute() or die "Fehler bei execute db: $DBI::errstr\n";
        $sth->finish();
        $dbh->disconnect;
}


sub get_host_ip {
	my ( $client_id,$ip_ocs_int ) = @_;
	my $ip_ref;
	my @values_ip;
        my $dbh = mysql_connection_gestioip();
	my $qip_ocs_int = $dbh->quote( $ip_ocs_int );
        my $sth = $dbh->prepare("SELECT h.ip, h.hostname, h.update_type, n.vigilada, h.range_id, h.host_descr, l.loc, c.cat, h.comentario FROM host h, net n, categorias c, locations l WHERE h.ip=$qip_ocs_int AND h.red_num = n.red_num AND c.id = h.categoria AND l.id = h.loc AND h.client_id = \"$client_id\"");
        $sth->execute() or print "error while prepareing query: $DBI::errstr\n";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @values_ip, [ @$ip_ref ];
        }
	$sth->finish();
        $dbh->disconnect;
        return @values_ip;
}

sub print_help {
	print "\nusage: ip_update_gestioip.pl [OPTIONS...]\n\n";
	print "-v, --verbose 		verbose\n";
	print "-V, --Version		print version and exit\n";
	print "-l, --log=logfile	logfile\n";
	print "-d, --disable_audit	disable auditing\n";
	print "-m, --mail		send the result by mail (mail_destinatarios)\n";
	print "-h, --help		help\n\n";
	print "\n\nconfiguration file: $conf\n\n";
	exit;
}

sub print_version {
	print "\n$0 Version $VERSION\n\n";
	exit 0;
}

sub send_mail {
	my $mailer = Mail::Mailer->new("");
	$mailer->open({	From	=> "$$mail_from",
			To	=> "$$mail_destinatarios",
			Subject	=> "Resultado update BBDD GestioIP OCS"
		     }) or die "error while sending mail: $!\n";
	open (LOG_MAIL,"<$log") or die "can not open log file: $!\n";
	while (<LOG_MAIL>) {
		print $mailer $_ if $_ !~ /$lang_vars{ignorado_message}/;
	}
	print $mailer "\n\n$count_entradas $lang_vars{entries_processed_message}\n";
	print $mailer "\n\n\n\n\n\n\n\n\n--------------------------------\n\n";
	print $mailer "$lang_vars{auto_mail_message}\n";
	$mailer->close;
	close LOG;
}

sub int_to_ip {
        my $ip_int=shift;
        my $ip_bin = ip_inttobin ($ip_int,4);
        my $ip_ad = ip_bintoip ($ip_bin,4);
        return $ip_ad;
}

sub ip_to_int {
        my $ip_ad=shift;
        my $ip_bin = ip_iptobin ($ip_ad,4);
        my $ip_int = ip_bintoint ($ip_bin,4);
        return $ip_int;
}

#sub resolve_ip {
#        my $ip=shift;
#        no strict 'subs';
#        my @h = gethostbyaddr(inet_aton($ip), AF_INET);
#        use strict;
#        return @h;
#}

sub resolve_name {
        my $hostname=shift;
        my @packed = gethostbyname($hostname);
	my $ip = inet_ntoa($packed[4]) if ($packed[0]);
        return $ip;
}

sub get_update_type {
	my ( $update_type_name ) = @_;
	my $update_type;
        my $dbh = mysql_connection_gestioip();
        my $sth = $dbh->prepare("SELECT id FROM update_type where type=\"$update_type_name\"
                        ") or print "Fehler bei select: $DBI::errstr\n";;
        $sth->execute();
        $update_type = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $update_type;
}

sub get_update_type_name {
	my ( $update_type_id ) = @_;
	my $update_type;
        my $dbh = mysql_connection_gestioip();
        my $sth = $dbh->prepare("SELECT type FROM update_type where id=\"$update_type_id\"
                        ") or print "Fehler bei select: $DBI::errstr\n";;
        $sth->execute();
        $update_type = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $update_type;
}

sub mysql_connection_ocs {
	my $dbh = DBI->connect("DBI:mysql:$params{sid_ocs}:$params{bbdd_host_ocs}:$params{bbdd_port_ocs}",$params{user_ocs},$params{pass_ocs}) or
	die "Cannot connect: ". $DBI::errstr;
	return $dbh;
}

sub mysql_connection_gestioip {
	my $dbh = DBI->connect("DBI:mysql:$params{sid_gestioip}:$params{bbdd_host_gestioip}:$params{bbdd_port_gestioip}",$params{user_gestioip},$params{pass_gestioip}) or
	die "Cannot connect: ". $DBI::errstr;
	return $dbh;
}

sub insert_audit_auto {
        my ($client_id,$event_class,$event_type,$event,$update_type_audit,$vars_file) = @_;
	my $user=$ENV{'USER'};
        my $mydatetime=time();
        my $dbh = mysql_connection_gestioip();
        my $qevent_class = $dbh->quote( $event_class );
        my $qevent_type = $dbh->quote( $event_type );
        my $qevent = $dbh->quote( $event );
        my $quser = $dbh->quote( $user );
        my $qupdate_type_audit = $dbh->quote( $update_type_audit );
        my $qmydatetime = $dbh->quote( $mydatetime );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("INSERT INTO audit_auto (event,user,event_class,event_type,update_type_audit,date,client_id) VALUES ($qevent,$quser,$qevent_class,$event_type,$qupdate_type_audit,$qmydatetime,$qclient_id)") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $sth->finish();
}

sub update_host_ping_info {
        my ( $client_id,$ip_int, $ping_result) = @_;
        my $dbh = mysql_connection_gestioip();
        my $qip_int = $dbh->quote( $ip_int );
        my $qmydatetime = $dbh->quote( time() );
        my $alive = $dbh->quote( $ping_result );
        my $sth;
        $sth = $dbh->prepare("UPDATE host SET alive=$alive, last_response=$qmydatetime WHERE ip=$qip_int AND client_id = \"$client_id\"") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $sth->finish();
        $dbh->disconnect;
}


sub get_vigilada_redes_hash {
	my ($client_id) = @_;
	my %redes;
	my $ip_ref;
        my $dbh = mysql_connection_gestioip();
	my $sth = $dbh->prepare("SELECT red,vigilada FROM net WHERE client_id = \"$client_id\"") or die "Can not execute statement:<p>$DBI::errstr";
	$sth->execute() or die "Can not execute statement:<p>$DBI::errstr";
	while ( $ip_ref = $sth->fetchrow_hashref ) {
		my $red = $ip_ref->{red};
		my $vigilada = $ip_ref->{vigilada};
		$redes{$red}="$vigilada";
	}
	$dbh->disconnect;
	return %redes;
}

sub check_for_reserved_range {
	my ( $client_id,$red_num ) = @_;
	my $ip_ref;
	my @ranges;
	my $dbh = mysql_connection_gestioip();
	my $sth = $dbh->prepare("SELECT red_num,start_ip,end_ip FROM ranges WHERE red_num = \"$red_num\" AND client_id = \"$client_id\"");
	$sth->execute() or print "error while prepareing query: $DBI::errstr\n";
	while ( $ip_ref = $sth->fetchrow_arrayref ) {
		push @ranges, [ @$ip_ref ];
	}
	$sth->finish();
	$dbh->disconnect;
	return @ranges;
}

sub count_clients {
        my $val;
        my $dbh = mysql_connection_gestioip();
        my $sth = $dbh->prepare("SELECT count(*) FROM clients
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub check_one_client_name {
        my ($client_name) = @_; 
        my $val;
        my $dbh = mysql_connection_gestioip();
        my $sth = $dbh->prepare("SELECT client FROM clients WHERE client=\"$client_name\"
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_client_id_one {
        my ($client_name) = @_; 
        my $val;
        my $dbh = mysql_connection_gestioip();
        my $sth = $dbh->prepare("SELECT id FROM clients
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_client_id_from_name {
        my ( $client_name ) = @_;
        my $val;
        my $dbh = mysql_connection_gestioip();
        my $qclient_name = $dbh->quote( $client_name );
        my $sth = $dbh->prepare("SELECT id FROM clients WHERE client=$qclient_name");
        $sth->execute() or  die "Can not execute statement:$sth->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_client_entries {
        my ( $client_id ) = @_;
        my @values;
        my $ip_ref;
        my $dbh = mysql_connection_gestioip();
        my $qclient_id = $dbh->quote( $client_id );
	my $sth;
        $sth = $dbh->prepare("SELECT c.client,ce.phone,ce.fax,ce.address,ce.comment,ce.contact_name_1,ce.contact_phone_1,ce.contact_cell_1,ce.contact_email_1,ce.contact_comment_1,ce.contact_name_2,ce.contact_phone_2,ce.contact_cell_2,ce.contact_email_2,ce.contact_comment_2,ce.contact_name_3,ce.contact_phone_3,ce.contact_cell_3,ce.contact_email_3,ce.contact_comment_3,ce.default_resolver,ce.dns_server_1,ce.dns_server_2,ce.dns_server_3 FROM clients c, client_entries ce WHERE c.id = ce.client_id AND c.id = $qclient_id") or die "Can not execute statement:$sth->errstr";
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @values, [ @$ip_ref ];
        }
        $dbh->disconnect;
        return @values;
}

sub get_version {
	my $val;
	my $dbh = mysql_connection_gestioip();
	my $sth = $dbh->prepare("SELECT version FROM global_config");
	$sth->execute() or  die "Can not execute statement:$sth->errstr";
	$val = $sth->fetchrow_array;
	$sth->finish();
	$dbh->disconnect;
	return $val;
}

sub get_host_id_from_ip_int {
        my ( $client_id,$ip_int ) = @_;
        my $val;
	my $dbh = mysql_connection_gestioip();
        my $qip_int = $dbh->quote( $ip_int );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth;
        $sth = $dbh->prepare("SELECT id FROM host WHERE ip=$qip_int AND client_id=$qclient_id") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub delete_custom_host_column_entry {
        my ( $client_id, $host_id ) = @_;
	my $dbh = mysql_connection_gestioip();
        my $qhost_id = $dbh->quote( $host_id );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth;
        $sth = $dbh->prepare("DELETE FROM custom_host_column_entries WHERE host_id = $qhost_id AND client_id = $qclient_id") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        $sth->finish();
        $dbh->disconnect;
}


__DATA__
